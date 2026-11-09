"""Immutable, explicitly published ndarray cache snapshots."""

from __future__ import annotations

import ctypes
import errno
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np


def _json(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _component(value, label):
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def _dtype(value):
    if value is None:
        return None
    try:
        dt = np.dtype(value)
    except (TypeError, ValueError):
        return str(value)
    return _json(dt.descr if dt.names else dt.str)


def _regular(path):
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"Published cache file missing or not regular: {path}")


class PublishedCache:
    def __init__(self, ctx, base):
        self.ctx = ctx
        self.base = Path(base).absolute()
        if self.base.is_symlink() or not self.base.is_dir():
            raise ValueError(f"Published cache base must be a directory: {self.base}")
        manifest_path = self.base / "manifest.json"
        _regular(manifest_path)
        with manifest_path.open(encoding="utf-8") as f:
            self.manifest = json.load(f)
        m = self.manifest
        if (
            not isinstance(m, dict)
            or set(m) != {"version", "run_id", "nodes", "run_config_hash"}
            or m["version"] != 1
            or not isinstance(m["nodes"], dict)
            or not m["nodes"]
        ):
            raise ValueError("Invalid published cache manifest")
        _component(m["run_id"], "run_id")
        if m["run_config_hash"] is not None and not isinstance(m["run_config_hash"], str):
            raise ValueError("Invalid published run-config state")
        for name, entry in m["nodes"].items():
            _component(name, "data name")
            if (
                not isinstance(entry, dict)
                or set(entry) != {"lineage", "dependencies", "dtype", "uses_run_config", "payload"}
                or not isinstance(entry["lineage"], dict)
                or not isinstance(entry["dependencies"], list)
                or not isinstance(entry["uses_run_config"], bool)
            ):
                raise ValueError(f"Invalid manifest node: {name}")
            for dep in entry["dependencies"]:
                _component(dep, "dependency")
                if dep not in m["nodes"]:
                    raise ValueError(f"Manifest dependency missing: {dep}")
            payload = entry["payload"]
            if payload is not None:
                if not isinstance(payload, dict) or set(payload) != {"key", "metadata", "size"}:
                    raise ValueError(f"Invalid manifest payload: {name}")
                _component(payload["key"], "cache key")
                if (
                    not isinstance(payload["metadata"], dict)
                    or not isinstance(payload["size"], int)
                    or isinstance(payload["size"], bool)
                    or payload["size"] <= 0
                ):
                    raise ValueError(f"Invalid manifest payload: {name}")

    def _graph(self, run_id, targets, selected=None):
        nodes = {}
        visited = set()

        def visit(name):
            _component(name, "data name")
            if name in visited:
                return
            visited.add(name)
            if name not in self.ctx._plugins:
                raise ValueError(f"No registered plugin for frozen dependency {name!r}")
            plugin = self.ctx._plugins[name]
            deps = self.ctx._plugin_domain.get_dependency_names(plugin, run_id=run_id)
            if selected is None or name in selected:
                nodes[name] = {
                    "lineage": _json(self.ctx.get_lineage(name)),
                    "dependencies": deps,
                    "dtype": _dtype(plugin.output_dtype),
                    "uses_run_config": bool(getattr(plugin, "uses_run_config", False)),
                    "payload": None,
                }
            for dep in deps:
                visit(dep)

        for target in targets:
            visit(target)
        return nodes

    def validate_request(self, run_id, target):
        m = self.manifest
        if run_id != m["run_id"]:
            raise ValueError(f"Published cache run_id mismatch: {run_id!r}")
        if getattr(self.ctx, "_last_run_id", None) != run_id:
            self.ctx._last_run_id = run_id
            self.ctx._invalidate_planning_caches()
        graph = self._graph(run_id, [target], selected=set(m["nodes"]))
        protected = set(graph)
        for name in protected:
            current = graph[name]
            saved = m["nodes"][name]
            if any(
                current[k] != saved[k]
                for k in ("lineage", "dependencies", "dtype", "uses_run_config")
            ):
                raise ValueError(f"Published cache identity mismatch for {name!r}")
            if saved["payload"] is not None:
                self._validate_payload(name, saved)
        if protected and any(m["nodes"][n]["uses_run_config"] for n in protected):
            current, _ = self.ctx._config_domain.compute_run_config_hash(run_id)
            if current is None or current != m["run_config_hash"]:
                raise ValueError("Published cache run-config mismatch or unavailable")
        return target in m["nodes"]

    def _validate_payload(self, name, node):
        payload = node["payload"]
        key = payload["key"]
        data_dir = self.base / "data"
        if data_dir.is_symlink() or not data_dir.is_dir():
            raise FileNotFoundError("Published cache data directory missing or not regular")
        data_path = data_dir / (key + ".bin")
        meta_path = data_dir / (key + ".json")
        _regular(data_path)
        _regular(meta_path)
        if data_path.stat().st_mode & 0o222 or meta_path.stat().st_mode & 0o222:
            raise ValueError(f"Published cache files must be read-only for {name!r}")
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
        if (
            meta != payload["metadata"]
            or meta.get("lineage") != node["lineage"]
            or meta.get("compressed", False)
            or meta.get("type") == "dataframe"
        ):
            raise ValueError(f"Published cache metadata mismatch for {name!r}")
        dtype = self.ctx._cache_domain._dtype_from_meta(meta)
        shape = meta.get("shape")
        if (
            dtype is None
            or dtype.hasobject
            or _dtype(dtype) != node["dtype"]
            or not isinstance(shape, list)
            or not shape
            or any(type(n) is not int or n <= 0 for n in shape)
            or type(meta.get("count")) is not int
            or meta["count"] != shape[0]
            or meta.get("itemsize") != dtype.itemsize
        ):
            raise ValueError(f"Published cache schema mismatch for {name!r}")
        expected = int(np.prod(shape, dtype=object)) * dtype.itemsize
        if payload["size"] != expected or data_path.stat().st_size != expected:
            raise ValueError(f"Published cache size mismatch for {name!r}")
        return data_path, dtype, shape

    def load(self, run_id, name):
        entry = self.manifest["nodes"][name]
        if entry["payload"] is None:
            return None
        path, dtype, shape = self._validate_payload(name, entry)
        result = self.ctx._get_data_from_memory(run_id, name)
        if (
            isinstance(result, np.memmap)
            and Path(result.filename) == path
            and not result.flags.writeable
        ):
            return result
        result = np.memmap(path, dtype=dtype, mode="r", shape=tuple(shape))
        self.ctx._set_data(run_id, name, result)
        return result


def publish(ctx, run_id, targets, destination):
    _component(run_id, "run_id")
    if isinstance(targets, str):
        targets = [targets]
    else:
        targets = list(targets)
    if not targets or len(set(targets)) != len(targets):
        raise ValueError("targets must be a non-empty sequence of unique data names")
    from .storage.memmap import MemmapStorage

    if (
        not isinstance(ctx.storage, MemmapStorage)
        or ctx._plugin_backends
        or ctx.storage.compression is not None
    ):
        raise ValueError("Publishing requires uncompressed MemmapStorage without plugin backends")
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    base = ctx._published_cache
    if base and os.path.commonpath(
        [os.path.realpath(destination), str(base.base.resolve())]
    ) == str(base.base.resolve()):
        raise ValueError("Cannot publish inside an existing base")
    if base is not None:
        if run_id != base.manifest["run_id"]:
            raise ValueError("Published cache run_id mismatch")
        # Validate all inherited entries against the current registrations.
        for name in base.manifest["nodes"]:
            base.validate_request(run_id, name)
    helper = base or object.__new__(PublishedCache)
    helper.ctx = ctx
    if getattr(ctx, "_last_run_id", None) != run_id:
        ctx._last_run_id = run_id
        ctx._invalidate_planning_caches()
    nodes = helper._graph(run_id, targets)
    if base:
        for name, entry in base.manifest["nodes"].items():
            if name not in nodes:
                nodes[name] = _json(entry)
            elif entry["payload"] is not None:
                nodes[name]["payload"] = _json(entry["payload"])
    has_run_config = any(n["uses_run_config"] for n in nodes.values())
    run_hash = None
    if has_run_config:
        run_hash, _ = ctx._config_domain.compute_run_config_hash(run_id)
        if run_hash is None:
            raise ValueError("Cannot verify run-config")
        if (
            base
            and any(n["uses_run_config"] for n in base.manifest["nodes"].values())
            and base.manifest["run_config_hash"] != run_hash
        ):
            raise ValueError("Published cache run-config mismatch")
        if any(
            t not in (base.manifest["nodes"] if base else {})
            or (base and base.manifest["nodes"].get(t, {}).get("payload") is None)
            for t in targets
        ):
            state_path = ctx._config_domain.get_run_config_hash_state_path(run_id)
            if not os.path.isfile(state_path):
                raise FileNotFoundError("Persisted run-config state is required to publish")
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict) or state.get("run_config_hash") != run_hash:
                raise ValueError("Persisted run-config state does not match current run-config")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".published-cache-", dir=destination.parent))
    locks = []
    try:
        data_dir = stage / "data"
        data_dir.mkdir()
        local_keys = sorted(
            _component(ctx.key_for(run_id, name), "cache key")
            for name in targets
            if not (
                base
                and name in base.manifest["nodes"]
                and base.manifest["nodes"][name]["payload"] is not None
            )
        )
        for key in local_keys:
            _, _, lock_path = ctx.storage._get_paths(key, run_id)
            if not Path(lock_path).parent.is_dir():
                raise FileNotFoundError(f"Cache directory missing for {key!r}")
            lock_fd = ctx.storage._acquire_lock(lock_path)
            if lock_fd is None:
                raise RuntimeError(f"Could not lock cache for {key!r}")
            locks.append((lock_fd, lock_path))
        for name, node in nodes.items():
            inherited = (
                base
                and name in base.manifest["nodes"]
                and base.manifest["nodes"][name]["payload"] is not None
            )
            if inherited:
                key = node["payload"]["key"]
                src_data, _, _ = base._validate_payload(name, base.manifest["nodes"][name])
                try:
                    os.link(src_data, data_dir / (key + ".bin"))
                except OSError as exc:
                    if exc.errno != errno.EXDEV:
                        raise
                    shutil.copyfile(src_data, data_dir / (key + ".bin"))
                    os.chmod(data_dir / (key + ".bin"), 0o444)
                shutil.copyfile(base.base / "data" / (key + ".json"), data_dir / (key + ".json"))
                os.chmod(data_dir / (key + ".json"), 0o444)
            elif name in targets:
                key = _component(ctx.key_for(run_id, name), "cache key")
                bin_path, meta_path, _ = ctx.storage._get_paths(key, run_id)
                _regular(Path(bin_path))
                _regular(Path(meta_path))
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                node["payload"] = {
                    "key": key,
                    "metadata": meta,
                    "size": os.path.getsize(bin_path),
                }
                shutil.copyfile(bin_path, data_dir / (key + ".bin"))
                shutil.copyfile(meta_path, data_dir / (key + ".json"))
                os.chmod(data_dir / (key + ".bin"), 0o444)
                os.chmod(data_dir / (key + ".json"), 0o444)
        manifest = {"version": 1, "run_id": run_id, "nodes": nodes, "run_config_hash": run_hash}
        with (stage / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, sort_keys=True, indent=2)
            f.write("\n")
        os.chmod(stage / "manifest.json", 0o444)
        candidate = PublishedCache(ctx, stage)
        for name, node in nodes.items():
            if node["payload"] is not None:
                candidate._validate_payload(name, node)
        if has_run_config and ctx._config_domain.compute_run_config_hash(run_id)[0] != run_hash:
            raise ValueError("Run-config changed during publication")
        # Linux renameat2 prevents replacing even an empty existing directory.
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        if renameat2(-100, os.fsencode(stage), -100, os.fsencode(destination), 1) != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err), str(destination))
    finally:
        for lock_fd, lock_path in reversed(locks):
            ctx.storage._release_lock(lock_fd, lock_path)
        if stage.exists():
            shutil.rmtree(stage)
    return destination
