from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any

import numpy as np

from .config import CompatManager, ConfigResolver, ConfigSource, ConfigValue, ResolvedConfig
from .plugins.core.base import Plugin


class ContextConfigDomain:
    """Configuration and run-config helpers used by Context."""

    def __init__(self, context: Any) -> None:
        self.ctx = context

    def ensure_config_resolver(self) -> ConfigResolver:
        if getattr(self.ctx, "_config_resolver", None) is None:
            if getattr(self.ctx, "_compat_manager", None) is None:
                self.ctx._compat_manager = CompatManager()
            self.ctx._config_resolver = ConfigResolver(compat_manager=self.ctx._compat_manager)
        return self.ctx._config_resolver

    def set_config(self, config: dict[str, Any], plugin_name: str | None = None) -> None:
        if plugin_name is not None:
            if plugin_name not in self.ctx._plugins:
                self.ctx.logger.warning(
                    "Plugin '%s' is not registered. Config will be set but may not be used by any plugin.",
                    plugin_name,
                )
            if plugin_name not in self.ctx.config:
                self.ctx.config[plugin_name] = {}
            if isinstance(self.ctx.config[plugin_name], dict):
                self.ctx.config[plugin_name].update(config)
            else:
                self.ctx.config[plugin_name] = {**config}
        else:
            self.ctx.config.update(config)

        self.ctx.clear_config_cache()
        self.ctx.clear_performance_caches()
        self.ctx._run_config_cache.clear()
        self.ctx._run_config_hash_loaded.clear()

    def raise_if_removed_data_name(self, data_name: str) -> None:
        replacement = self.ctx._REMOVED_DATA_NAME_ALIASES.get(data_name)
        if replacement is None:
            return
        raise ValueError(
            f"Data name '{data_name}' has been removed. Please use '{replacement}' instead."
        )

    def get_config_value(
        self,
        plugin: Plugin,
        name: str,
        adapter_name: str | None = None,
    ) -> ConfigValue:
        if adapter_name is None:
            adapter_name = self.resolve_adapter_name_for_plugin(plugin)
        resolver = self.ensure_config_resolver()
        return resolver.resolve_value(
            plugin=plugin,
            name=name,
            config=self.ctx.config,
            adapter_name=adapter_name,
        )

    def get_config(self, plugin: Plugin, name: str) -> Any:
        return self.get_config_value(plugin, name).value

    def resolve_config_value(self, plugin: Plugin, name: str) -> Any:
        return self.get_config(plugin, name)

    def has_explicit_config(
        self,
        plugin: Plugin,
        name: str,
        adapter_name: str | None = None,
    ) -> bool:
        try:
            cv = self.get_config_value(plugin, name, adapter_name=adapter_name)
        except KeyError:
            return False
        return cv.source == ConfigSource.EXPLICIT

    def resolve_adapter_name_for_plugin(
        self,
        plugin: Plugin,
        adapter_name: str | None = None,
    ) -> str | None:
        resolved_adapter = (
            adapter_name if adapter_name is not None else self.ctx.config.get("daq_adapter")
        )
        if "daq_adapter" not in plugin.options:
            return resolved_adapter
        try:
            resolver = self.ensure_config_resolver()
            cv = resolver.resolve_value(
                plugin=plugin,
                name="daq_adapter",
                config=self.ctx.config,
                adapter_name=None,
            )
        except KeyError:
            return resolved_adapter
        if cv.value is not None:
            return cv.value
        return resolved_adapter

    def get_resolved_config(
        self,
        plugin: Plugin | str,
        adapter_name: str | None = None,
    ) -> ResolvedConfig:
        if isinstance(plugin, str):
            if plugin not in self.ctx._plugins:
                raise KeyError(f"Plugin '{plugin}' is not registered")
            plugin = self.ctx._plugins[plugin]

        if adapter_name is None:
            adapter_name = self.resolve_adapter_name_for_plugin(plugin)

        resolver = self.ensure_config_resolver()
        return resolver.resolve(plugin=plugin, config=self.ctx.config, adapter_name=adapter_name)

    def make_config_signature(self, raw_config: dict[str, Any]) -> str:
        def default(value: Any) -> str:
            if isinstance(value, np.ndarray):
                return value.tobytes().hex()
            return repr(value)

        normalized = {name: raw_config[name] for name in sorted(raw_config)}
        payload = json.dumps(normalized, sort_keys=True, default=default)
        return hashlib.sha256(payload.encode()).hexdigest()

    def make_resolved_config_signature(self, resolved: ResolvedConfig) -> str:
        payload = {"__adapter__": resolved.adapter_name}
        payload.update(resolved.to_dict())
        return self.make_config_signature(payload)

    def ensure_plugin_config_validated(self, plugin: Plugin) -> dict[str, Any]:
        resolved = self.get_resolved_config(plugin)
        signature = self.make_resolved_config_signature(resolved)
        cache_key = (plugin.provides, signature)
        if cache_key in self.ctx._resolved_config_cache:
            return self.ctx._resolved_config_cache[cache_key]

        validated = resolved.to_dict()
        self.ctx._resolved_config_cache[cache_key] = validated
        return validated

    def get_custom_config_sync_path(self, run_id: str) -> str:
        configured_path = self.ctx.config.get("custom_config_json_path")
        if configured_path:
            try:
                return str(configured_path).format(run_id=run_id)
            except Exception:
                return str(configured_path)
        return ""

    def sync_custom_config_json(self, run_id: str, data_name: str) -> None:
        path = self.get_custom_config_sync_path(run_id)
        if not path:
            return

        payload = {
            "run_id": run_id,
            "requested_data_name": data_name,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "custom_config": self.ctx.config.copy(),
        }
        if isinstance(payload["custom_config"], dict):
            payload["custom_config"].pop("custom_config_json_path", None)

        try:
            dir_path = os.path.dirname(path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            temp_path = path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)
                fh.write("\n")
            os.replace(temp_path, path)
        except Exception as exc:
            self.ctx.logger.warning("Failed to sync custom config JSON to %s: %s", path, exc)

    def get_run_config_filename(self) -> str:
        value = self.ctx.config.get("run_config_filename", "run_config.json")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "run_config.json"

    def get_default_run_config_path_template(self) -> str:
        data_root = os.path.normpath(str(self.ctx.config.get("data_root", "DAQ")))
        data_root_parent = os.path.dirname(data_root)
        return os.path.join(data_root_parent, "{run_id}", self.get_run_config_filename())

    def format_run_config_path(self, path_template: str, run_id: str) -> str:
        data_root = str(self.ctx.config.get("data_root", "DAQ"))
        data_root_norm = os.path.normpath(data_root)
        data_root_parent = os.path.dirname(data_root_norm)
        filename = self.get_run_config_filename()
        return str(
            path_template.format(
                run_id=run_id,
                run_name=run_id,
                data_root=data_root,
                data_root_parent=data_root_parent,
                filename=filename,
            )
        )

    def resolve_run_config_path(self, run_id: str) -> str:
        path_template = self.ctx.config.get("run_config_path")
        if isinstance(path_template, str) and path_template.strip():
            path_template = path_template.strip()
            try:
                return self.format_run_config_path(path_template, run_id)
            except Exception:
                self.ctx.logger.warning(
                    "Invalid run_config_path '%s'; falling back to legacy/default layout.",
                    path_template,
                )

        path_template = self.ctx.config.get("run_config_path_template")
        if isinstance(path_template, str) and path_template.strip():
            path_template = path_template.strip()
            try:
                return self.format_run_config_path(path_template, run_id)
            except Exception:
                self.ctx.logger.warning(
                    "Invalid run_config_path_template '%s'; falling back to default layout.",
                    path_template,
                )

        return self.format_run_config_path(self.get_default_run_config_path_template(), run_id)

    def compute_run_config_hash(self, run_id: str) -> tuple[str | None, str]:
        config_path = self.resolve_run_config_path(run_id)
        if not os.path.exists(config_path):
            return "missing", config_path

        try:
            hasher = hashlib.sha1()
            with open(config_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    hasher.update(chunk)
            return "sha1:" + hasher.hexdigest(), config_path
        except Exception as exc:
            self.ctx.logger.warning("Failed to hash run config '%s': %s", config_path, exc)
            return None, config_path

    def get_run_config_hash_state_path(self, run_id: str) -> str:
        try:
            if hasattr(self.ctx.storage, "get_run_data_dir"):
                base_dir = self.ctx.storage.get_run_data_dir(run_id)
            else:
                base_dir = os.path.join(self.ctx.storage_dir, run_id, "_cache")
        except Exception:
            base_dir = os.path.join(self.ctx.storage_dir, run_id, "_cache")
        return os.path.join(base_dir, "_run_config_state.json")

    def load_previous_run_config_hash(self, run_id: str) -> str | None:
        if run_id in self.ctx._run_config_hash_loaded:
            return self.ctx._run_config_hash_cache.get(run_id)

        state_path = self.get_run_config_hash_state_path(run_id)
        previous_hash = None
        if os.path.exists(state_path):
            try:
                with open(state_path, encoding="utf-8") as fh:
                    payload = json.load(fh)
                if isinstance(payload, dict):
                    hash_value = payload.get("run_config_hash")
                    if isinstance(hash_value, str):
                        previous_hash = hash_value
            except Exception as exc:
                self.ctx.logger.warning(
                    "Failed to read run config hash state '%s': %s", state_path, exc
                )

        self.ctx._run_config_hash_loaded.add(run_id)
        if previous_hash is not None:
            self.ctx._run_config_hash_cache[run_id] = previous_hash
        return previous_hash

    def save_run_config_hash(self, run_id: str, config_path: str, config_hash: str) -> None:
        state_path = self.get_run_config_hash_state_path(run_id)
        payload = {
            "run_id": run_id,
            "run_config_path": config_path,
            "run_config_hash": config_hash,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            temp_path = state_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(temp_path, state_path)
        except Exception as exc:
            self.ctx.logger.warning(
                "Failed to persist run config hash to '%s': %s", state_path, exc
            )

    def get_run_config_roots(self) -> list[str]:
        roots = []
        for name, plugin in self.ctx._plugins.items():
            if bool(getattr(plugin, "uses_run_config", False)):
                roots.append(name)
        return roots

    def invalidate_run_config_related_cache(self, run_id: str) -> None:
        targets = self.get_run_config_roots()
        for target in targets:
            try:
                self.ctx.clear_cache_for(run_id, target, downstream=True, verbose=False)
            except Exception as exc:
                self.ctx.logger.warning(
                    "Failed to clear run config related cache for (%s, %s): %s",
                    run_id,
                    target,
                    exc,
                )

    def maybe_invalidate_run_config_cache(self, run_id: str) -> None:
        current_hash, config_path = self.compute_run_config_hash(run_id)
        if current_hash is None:
            return

        previous_hash = self.load_previous_run_config_hash(run_id)
        if previous_hash is None:
            self.ctx._run_config_hash_cache[run_id] = current_hash
            self.save_run_config_hash(run_id, config_path, current_hash)
            return
        if previous_hash == current_hash:
            return

        self.ctx.logger.info(
            "Detected run_config change for run '%s' (%s -> %s); invalidating related caches.",
            run_id,
            previous_hash,
            current_hash,
        )
        self.invalidate_run_config_related_cache(run_id)
        self.ctx._run_config_cache.pop(run_id, None)
        self.ctx._run_config_hash_cache[run_id] = current_hash
        self.save_run_config_hash(run_id, config_path, current_hash)

    def get_run_config(self, run_id: str, refresh: bool = False) -> dict[str, Any]:
        current_hash, config_path = self.compute_run_config_hash(run_id)
        if current_hash is None:
            return {}

        cached = self.ctx._run_config_cache.get(run_id)
        cached_hash = self.ctx._run_config_hash_cache.get(run_id)
        if not refresh and cached is not None and cached_hash == current_hash:
            return cached

        if current_hash == "missing":
            result = {}
        else:
            result = {}
            try:
                with open(config_path, encoding="utf-8") as fh:
                    payload = json.load(fh)
                if isinstance(payload, dict):
                    result = payload
                else:
                    self.ctx.logger.warning(
                        "Run config file '%s' must contain a JSON object; got %s.",
                        config_path,
                        type(payload).__name__,
                    )
            except Exception as exc:
                self.ctx.logger.warning("Failed to read run config '%s': %s", config_path, exc)

        self.ctx._run_config_cache[run_id] = result
        self.ctx._run_config_hash_cache[run_id] = current_hash
        return result

    def get_plugin_run_config(self, plugin: Plugin | str, run_id: str) -> dict[str, Any]:
        plugin_name = plugin if isinstance(plugin, str) else plugin.provides
        run_config = self.get_run_config(run_id)
        plugins_block = run_config.get("plugins", {})
        if isinstance(plugins_block, dict):
            plugin_block = plugins_block.get(plugin_name)
            if isinstance(plugin_block, dict):
                return plugin_block

        plugin_config = self.ctx.config.get(plugin_name)
        if isinstance(plugin_config, dict):
            runs_block = plugin_config.get("runs", {})
            if isinstance(runs_block, dict):
                run_block = runs_block.get(run_id)
                if isinstance(run_block, dict):
                    return run_block
        return {}

    def show_resolved_config(
        self,
        plugin: Plugin | str | None = None,
        verbose: bool = True,
        adapter_name: str | None = None,
    ) -> None:
        if adapter_name is None:
            adapter_name = self.ctx.config.get("daq_adapter")

        if plugin is None:
            plugins_to_show = list(self.ctx._plugins.values())
        elif isinstance(plugin, str):
            if plugin not in self.ctx._plugins:
                print(f"Plugin '{plugin}' is not registered")
                return
            plugins_to_show = [self.ctx._plugins[plugin]]
        else:
            plugins_to_show = [plugin]

        for p in plugins_to_show:
            resolved = self.get_resolved_config(p, adapter_name=adapter_name)
            print(resolved.summary(verbose=verbose))
            print()

    def prepare_request(self, run_id: str, data_name: str) -> None:
        self.raise_if_removed_data_name(data_name)
        self.sync_custom_config_json(run_id, data_name)
        self.ctx._last_run_id = run_id
        self.maybe_invalidate_run_config_cache(run_id)
