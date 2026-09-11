"""Next static-export adapter and wheel-safe prebuilt-site publisher.

``waveform-docs generate site-web`` is intentionally the only HTML-producing
command.  In a source checkout this adapter builds the versioned site model,
passes its path to the Next application, and validates the resulting export.
When imported from an installed wheel (where the repository and Node are not
available), it copies a packaged prebuilt export after checking its SHA-256
manifest.  There is no Jinja or HTML fallback in either path.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any
from urllib.parse import unquote, urlparse

from .site_model import (
    SITE_MODEL_ENV,
    SITE_MODEL_ENV_ALIASES,
    SITE_MODEL_EXPORT_ENV,
    SITE_MODEL_FILENAME,
    SiteModelError,
    build_site_model,
    load_site_model,
    route_without_leading_slash,
    validate_site_model,
    write_site_model,
)

SITE_MANIFEST_FILENAME = "site-manifest.json"
SITE_MANIFEST_SCHEMA = "site-web/v1"
SITE_MANIFEST_ENV = "WAVEFORM_DOCS_PREBUILT_DIR"
SITE_PUBLISH_MAX_BYTES = 83_886_080
DEFAULT_APP_RELATIVE = Path("docs") / "site-next"
# Keep the packaged export separate from the ``site_web.py`` module.  A
# sibling directory named ``site_web`` makes import resolution ambiguous in a
# wheel and is surprising to package walkers.
DEFAULT_PREBUILT_RELATIVE = Path("waveform_analysis") / "documentation" / "site_dist"


class SiteWebBuildError(RuntimeError):
    """Raised when the Next build or static export contract fails."""


class SiteExportValidationError(ValueError):
    """Raised for unsafe, incomplete, or non-offline static exports."""


class _ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, str, str]] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs if value is not None}
        for name in ("href", "src"):
            value = values.get(name)
            if value:
                self.references.append((tag.lower(), name, value))
        for name in ("id", "name"):
            value = values.get(name)
            if value:
                self.anchors.add(value)


def _safe_relative_path(value: str, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SiteExportValidationError(f"{field} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise SiteExportValidationError(f"{field} escapes its root: {value!r}")
    return path


def _resolve_export_reference(root: Path, page: Path, reference: str) -> tuple[Path | None, str]:
    parsed = urlparse(reference)
    if parsed.scheme or parsed.netloc:
        return None, unquote(parsed.fragment)
    path_text = unquote(parsed.path)
    target = root / path_text.lstrip("/") if path_text.startswith("/") else page.parent / path_text
    target = target.resolve()
    if target.is_dir():
        target /= "index.html"
    elif not target.exists() and path_text and not Path(path_text).suffix:
        # A trailing-slash Next route is physically an index.html directory.
        candidate = target / "index.html"
        if candidate.is_file():
            target = candidate
    return target, unquote(parsed.fragment)


def _route_target(root: Path, route: str) -> Path:
    path = route_without_leading_slash(route)
    if not path:
        return (root / "index.html").resolve()
    directory = (root / path).resolve()
    if directory.is_dir():
        return directory / "index.html"
    if (directory / "index.html").is_file():
        return directory / "index.html"
    return directory


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def is_next_rsc_text(path: Path | str) -> bool:
    """Return whether *path* is one of Next's generated RSC text artifacts.

    Files whose basename starts with ``__next.`` are unambiguously generated
    route payloads.  A bare ``index.txt`` is intentionally not classified here:
    it is only removed by :func:`filter_next_rsc_text_files` when the same
    directory also contains an unambiguous ``__next.*.txt`` companion.  This
    keeps ordinary user-authored ``index.txt`` assets intact.
    """

    candidate = Path(path)
    return candidate.suffix == ".txt" and candidate.name.startswith("__next.")


def filter_next_rsc_text_files(root: Path) -> list[Path]:
    """Remove only known Next RSC ``.txt`` files and return removed paths."""

    output = Path(root).resolve()
    if not output.is_dir():
        raise SiteExportValidationError(f"static export directory does not exist: {root}")
    files = list(_iter_files(output))
    next_payload_directories = {path.parent for path in files if is_next_rsc_text(path)}
    removed: list[Path] = []
    for path in files:
        is_companion_index = path.name == "index.txt" and path.parent in next_payload_directories
        if not is_next_rsc_text(path) and not is_companion_index:
            continue
        path.unlink()
        removed.append(path.relative_to(output))
    return removed


def static_file_inventory(
    directory: Path, *, include_manifest: bool = False
) -> list[dict[str, Any]]:
    """Return a stable relative-path/size/SHA-256 inventory.

    The manifest itself is excluded by default so its fingerprint cannot be
    self-referential.  The published byte budget is intentionally calculated
    separately over the actual root and therefore includes the manifest.
    """

    root = Path(directory).resolve()
    if not root.is_dir():
        raise SiteExportValidationError(f"static export directory does not exist: {directory}")
    entries: list[dict[str, Any]] = []
    for path in _iter_files(root):
        if not include_manifest and path == root / SITE_MANIFEST_FILENAME:
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise SiteExportValidationError(f"export file escapes output directory: {path}")
        content = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )
    return entries


def static_export_fingerprint(
    directory: Path, *, entries: Iterable[Mapping[str, Any]] | None = None
) -> str:
    """Hash a deterministic inventory, excluding ``site-manifest.json``."""

    inventory = list(entries) if entries is not None else static_file_inventory(directory)
    canonical_lines = []
    for entry in sorted(inventory, key=lambda item: str(item["path"])):
        canonical_lines.append(
            json.dumps(
                {
                    "path": str(entry["path"]),
                    "sha256": str(entry["sha256"]),
                    "size": int(entry["size"]),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    return hashlib.sha256(("\n".join(canonical_lines) + "\n").encode("utf-8")).hexdigest()


def validate_published_site_budget(
    directory: Path, *, max_bytes: int = SITE_PUBLISH_MAX_BYTES
) -> dict[str, Any]:
    """Enforce the hard published-root byte budget, including the manifest."""

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    root = Path(directory).resolve()
    if not root.is_dir():
        raise SiteExportValidationError(f"static export directory does not exist: {directory}")
    files: list[tuple[str, int]] = []
    for path in _iter_files(root):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise SiteExportValidationError(f"export file escapes output directory: {path}")
        files.append((path.relative_to(root).as_posix(), path.stat().st_size))
    total_bytes = sum(size for _path, size in files)
    largest = sorted(files, key=lambda item: (-item[1], item[0]))
    if total_bytes > max_bytes:
        contributors = ", ".join(f"{path}={size} bytes" for path, size in largest[:5])
        raise SiteExportValidationError(
            "published site exceeds hard byte budget "
            f"{max_bytes} bytes: total={total_bytes} bytes; "
            f"largest contributors: {contributors}"
        )
    return {
        "total_bytes": total_bytes,
        "max_bytes": max_bytes,
        "file_count": len(files),
        "largest": [{"path": path, "size": size} for path, size in largest[:5]],
    }


def validate_static_export(
    output_dir: Path,
    *,
    model: Mapping[str, Any] | None = None,
    require_model: bool = False,
) -> None:
    """Validate route completeness, local links, fragments, and path bounds."""

    root = Path(output_dir).resolve()
    if not root.is_dir():
        raise SiteExportValidationError(f"static export directory does not exist: {output_dir}")
    if not (root / "index.html").is_file():
        raise SiteExportValidationError("static export is missing index.html")
    if model is not None:
        validate_site_model(model)
    elif require_model:
        raise SiteExportValidationError("site-web export is missing the site-model/v1 input")

    for path in _iter_files(root):
        if not path.resolve().is_relative_to(root):
            raise SiteExportValidationError(f"export file escapes output directory: {path}")
    pages = sorted(root.rglob("*.html"))
    anchors: dict[Path, set[str]] = {}
    parsers: dict[Path, _ReferenceParser] = {}
    errors: list[str] = []
    for page in pages:
        parser = _ReferenceParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            errors.append(f"{page.relative_to(root)} is not UTF-8 HTML: {exc}")
            continue
        anchors[page.resolve()] = parser.anchors
        parsers[page.resolve()] = parser

    for page in pages:
        parser = parsers.get(page.resolve())
        if parser is None:
            continue
        for _tag, attribute, reference in parser.references:
            parsed = urlparse(reference)
            if parsed.scheme or parsed.netloc:
                if attribute == "src" and parsed.scheme in {"http", "https"}:
                    errors.append(f"{page.relative_to(root)} -> external asset {reference}")
                continue
            path_text = unquote(parsed.path)
            # Physical index.html files are implementation details and must not
            # leak into public navigation or search links.
            if attribute == "href" and (path_text.endswith(".html") or ".html/" in path_text):
                errors.append(f"{page.relative_to(root)} -> legacy .html route {reference}")
                continue
            target, fragment = _resolve_export_reference(root, page, reference)
            if target is None:
                continue
            if not target.is_relative_to(root) or not target.is_file():
                errors.append(f"{page.relative_to(root)} -> missing local target {reference}")
                continue
            if fragment and target.suffix.lower() in {".html", ".htm"}:
                page_anchors = anchors.get(target.resolve(), set())
                if not any(anchor.casefold() == fragment.casefold() for anchor in page_anchors):
                    errors.append(f"{page.relative_to(root)} -> missing fragment {reference}")

    if model is not None:
        for record in model.get("routes", []):
            route = record.get("path") if isinstance(record, Mapping) else None
            if not isinstance(route, str):
                continue
            target = _route_target(root, route)
            if not target.is_relative_to(root) or not target.is_file():
                errors.append(f"model route {route} is not present in static export")
        model_path = root / SITE_MODEL_FILENAME
        if model_path.is_file():
            try:
                load_site_model(model_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{SITE_MODEL_FILENAME} is invalid: {exc}")
    if errors:
        preview = "; ".join(errors[:10])
        suffix = f"; and {len(errors) - 10} more" if len(errors) > 10 else ""
        raise SiteExportValidationError(f"invalid static site export: {preview}{suffix}")


def _manifest_entries(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    schema = manifest.get("schema", manifest.get("manifest_schema"))
    if schema not in {None, SITE_MANIFEST_SCHEMA}:
        raise SiteExportValidationError(f"unsupported prebuilt site manifest schema: {schema!r}")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise SiteExportValidationError(
            "prebuilt site manifest must contain a non-empty files list"
        )
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, Mapping):
            raise SiteExportValidationError(f"manifest.files[{index}] must be an object")
        path_value = item.get("path")
        path = _safe_relative_path(path_value, field=f"manifest.files[{index}].path")
        key = path.as_posix()
        if key in seen:
            raise SiteExportValidationError(f"manifest contains duplicate file {key!r}")
        seen.add(key)
        digest = item.get("sha256", item.get("hash"))
        if not isinstance(digest, str) or len(digest) != 64:
            raise SiteExportValidationError(f"manifest.files[{index}] has an invalid sha256")
        size = item.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise SiteExportValidationError(f"manifest.files[{index}] has an invalid size")
        normalized.append({"path": path, "sha256": digest, "size": size})
    return normalized


def _read_prebuilt_manifest(directory: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = directory / SITE_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise SiteExportValidationError(f"prebuilt site is missing {SITE_MANIFEST_FILENAME}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SiteExportValidationError(f"invalid prebuilt site manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise SiteExportValidationError("prebuilt site manifest must be an object")
    return manifest, _manifest_entries(manifest)


def write_prebuilt_manifest(directory: Path, *, max_bytes: int = SITE_PUBLISH_MAX_BYTES) -> Path:
    """Write a deterministic hash manifest for a validated static export."""

    root = Path(directory).resolve()
    if not root.is_dir() or not (root / "index.html").is_file():
        raise SiteExportValidationError(f"prebuilt site is incomplete: {root}")
    entries = static_file_inventory(root)
    manifest = {
        "content_bytes": sum(entry["size"] for entry in entries),
        "file_count": len(entries),
        "fingerprint": static_export_fingerprint(root, entries=entries),
        "hash_algorithm": "sha256",
        "schema": SITE_MANIFEST_SCHEMA,
        "files": entries,
    }
    destination = root / SITE_MANIFEST_FILENAME
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    validate_published_site_budget(root, max_bytes=max_bytes)
    return destination


def copy_prebuilt_site(source_dir: Path, output_dir: Path) -> dict[str, Path]:
    """Copy a packaged static export after verifying every manifest hash."""

    source = Path(source_dir).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_dir():
        raise SiteExportValidationError(f"prebuilt site directory does not exist: {source}")
    manifest, entries = _read_prebuilt_manifest(source)
    listed = {entry["path"].as_posix() for entry in entries}
    actual = {
        path.relative_to(source).as_posix()
        for path in _iter_files(source)
        if path != source / SITE_MANIFEST_FILENAME
    }
    if actual != listed - {SITE_MANIFEST_FILENAME}:
        missing = sorted((listed - {SITE_MANIFEST_FILENAME}) - actual)
        extra = sorted(actual - (listed - {SITE_MANIFEST_FILENAME}))
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("unlisted=" + ",".join(extra))
        raise SiteExportValidationError(
            "prebuilt site file set does not match manifest: " + "; ".join(details)
        )
    destination.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        relative = entry["path"]
        if relative.as_posix() == SITE_MANIFEST_FILENAME:
            continue
        source_path = (source / relative).resolve()
        if not source_path.is_relative_to(source) or not source_path.is_file():
            raise SiteExportValidationError(f"manifest file is outside prebuilt root: {relative}")
        content = source_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if len(content) != entry["size"] or digest != entry["sha256"]:
            raise SiteExportValidationError(f"hash manifest mismatch for {relative}")
        target = (destination / relative).resolve()
        if not target.is_relative_to(destination):
            raise SiteExportValidationError(f"prebuilt file escapes output root: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
    expected_fingerprint = manifest.get("fingerprint")
    if expected_fingerprint is not None:
        if not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64:
            raise SiteExportValidationError("prebuilt site manifest has an invalid fingerprint")
        actual_fingerprint = static_export_fingerprint(source, entries=entries)
        if actual_fingerprint != expected_fingerprint:
            raise SiteExportValidationError(
                "prebuilt site manifest fingerprint mismatch: "
                f"{actual_fingerprint} != {expected_fingerprint}"
            )
    filter_next_rsc_text_files(destination)
    if not (destination / "index.html").is_file():
        raise SiteExportValidationError("prebuilt site is missing index.html")
    model = None
    model_path = destination / SITE_MODEL_FILENAME
    if model_path.is_file():
        model = load_site_model(model_path)
    validate_static_export(destination, model=model)
    manifest_path = write_prebuilt_manifest(destination)
    return (
        {
            "SITE_INDEX": destination / "index.html",
            "SITE_MODEL": model_path,
            "SITE_MANIFEST": manifest_path,
        }
        if model_path.is_file()
        else {"SITE_INDEX": destination / "index.html", "SITE_MANIFEST": manifest_path}
    )


def locate_prebuilt_site(*, project_root: Path | None = None, explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    configured = os.environ.get(SITE_MANIFEST_ENV)
    if configured:
        return Path(configured).resolve()
    package_root = Path(__file__).resolve().parent / "site_dist"
    if package_root.is_dir():
        return package_root
    root = Path(project_root or Path.cwd()).resolve()
    return (root / DEFAULT_PREBUILT_RELATIVE).resolve()


@dataclass
class NextSiteBuilder:
    """Build the model and static export in a source checkout."""

    project_root: Path | None = None
    app_root: Path | None = None
    install_dependencies: bool | None = None
    command_runner: Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        root = Path(self.project_root or Path.cwd()).resolve()
        self.project_root = root
        self.app_root = Path(self.app_root or root / DEFAULT_APP_RELATIVE).resolve()

    def _run(self, command: list[str], *, env: Mapping[str, str]) -> Any:
        runner = self.command_runner or subprocess.run
        try:
            return runner(command, cwd=str(self.app_root), env=dict(env), check=True, text=True)
        except FileNotFoundError as exc:
            raise SiteWebBuildError(
                f"required Node command is unavailable: {' '.join(command)}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise SiteWebBuildError(
                f"Next static build command failed ({exc.returncode}): {' '.join(command)}"
            ) from exc

    def _build_model(self, path: Path) -> dict[str, Any]:
        try:
            model = build_site_model(self.project_root)
            write_site_model(model, path)
            return model
        except Exception as exc:
            if isinstance(exc, SiteModelError):
                raise
            raise SiteWebBuildError(f"could not build site-model/v1: {exc}") from exc

    def _export_directory(
        self,
        requested: Path,
        started_ns: int,
        before_mtimes: Mapping[Path, int | None],
    ) -> Path:
        candidates = [
            requested,
            self.app_root / "out",
            self.app_root / "export",
            self.app_root / "dist",
        ]
        for candidate in candidates:
            if candidate.is_dir() and (candidate / "index.html").is_file():
                # ``out``/``export``/``dist`` may be leftovers from an older
                # invocation.  Accept a fallback only when this invocation
                # created or changed that directory after the build began.
                before = before_mtimes.get(candidate)
                current = candidate.stat().st_mtime_ns
                if (
                    candidate == requested
                    or before is None
                    or (current >= started_ns and current > before)
                ):
                    return candidate.resolve()
        raise SiteWebBuildError(
            "Next build completed without a static export containing index.html; "
            "configure WAVEFORM_SITE_EXPORT_DIR in docs/site-next/next.config"
        )

    def generate(self, output_dir: Path) -> dict[str, Path]:
        if not self.app_root.is_dir() or not (self.app_root / "package.json").is_file():
            raise SiteWebBuildError(
                f"source checkout is missing Next app at {self.app_root}; no Jinja fallback is available"
            )
        output = Path(output_dir).resolve()
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".waveform-site-model-", dir=str(output.parent)
        ) as temporary:
            model_path = Path(temporary) / SITE_MODEL_FILENAME
            model = self._build_model(model_path)
            export_path = Path(temporary) / "export"
            export_path.mkdir()
            env = os.environ.copy()
            env["NEXT_TELEMETRY_DISABLED"] = "1"
            for name in SITE_MODEL_ENV_ALIASES:
                env[name] = str(model_path)
            env["WAVEFORM_SITE_MODEL_SCHEMA"] = SITE_MODEL_ENV
            env[SITE_MODEL_EXPORT_ENV] = str(export_path)
            env["WAVEFORM_SITE_EXPORT_ROOT"] = str(export_path)
            node_modules = self.app_root / "node_modules"
            install = self.install_dependencies
            if install:
                self._run(["npm", "ci", "--ignore-scripts"], env=env)
            if not node_modules.is_dir():
                raise SiteWebBuildError(
                    "Next dependencies are not installed at "
                    f"{node_modules}; run `npm ci` in {self.app_root} "
                    "(or pass install_dependencies=True explicitly) before "
                    "waveform-docs generate site-web"
                )
            expected_out = self.app_root / "out"
            if expected_out.is_symlink() or (expected_out.exists() and not expected_out.is_dir()):
                raise SiteWebBuildError(
                    f"Next output path must be a normal directory: {expected_out}"
                )
            if expected_out.is_dir():
                shutil.rmtree(expected_out)
            candidates = [
                export_path,
                self.app_root / "out",
                self.app_root / "export",
                self.app_root / "dist",
            ]
            before_mtimes = {
                candidate: candidate.stat().st_mtime_ns if candidate.is_dir() else None
                for candidate in candidates
            }
            started_ns = time.time_ns()
            self._run(["npm", "run", "check"], env=env)
            self._run(["npm", "run", "build"], env=env)
            export_source = self._export_directory(export_path, started_ns, before_mtimes)
            shutil.copytree(export_source, output, dirs_exist_ok=True)
            filter_next_rsc_text_files(output)
            # The model remains inspectable in the published export even when
            # the app bundles it into JS during build.
            published_model = output / SITE_MODEL_FILENAME
            if not published_model.exists():
                shutil.copy2(model_path, published_model)
        validate_static_export(output, model=model, require_model=True)
        manifest_path = write_prebuilt_manifest(output)
        results: dict[str, Path] = {
            "SITE_INDEX": output / "index.html",
            "SITE_MODEL": output / SITE_MODEL_FILENAME,
            "SITE_MANIFEST": manifest_path,
        }
        return results


@dataclass
class SiteWebBuilder:
    """Select source Next build or installed-wheel prebuilt copy."""

    project_root: Path | None = None
    app_root: Path | None = None
    prebuilt_dir: Path | None = None
    command_runner: Callable[..., Any] | None = None
    install_dependencies: bool | None = None

    def generate(self, output_dir: Path) -> dict[str, Path]:
        root = Path(self.project_root or Path.cwd()).resolve()
        app = Path(self.app_root or root / DEFAULT_APP_RELATIVE).resolve()
        if app.is_dir() and (app / "package.json").is_file():
            return NextSiteBuilder(
                project_root=root,
                app_root=app,
                command_runner=self.command_runner,
                install_dependencies=self.install_dependencies,
            ).generate(output_dir)
        source = locate_prebuilt_site(project_root=root, explicit=self.prebuilt_dir)
        return copy_prebuilt_site(source, output_dir)


__all__ = [
    "DEFAULT_APP_RELATIVE",
    "SITE_MANIFEST_ENV",
    "SITE_MANIFEST_FILENAME",
    "SITE_MANIFEST_SCHEMA",
    "SITE_PUBLISH_MAX_BYTES",
    "NextSiteBuilder",
    "SiteExportValidationError",
    "SiteWebBuildError",
    "SiteWebBuilder",
    "copy_prebuilt_site",
    "filter_next_rsc_text_files",
    "is_next_rsc_text",
    "locate_prebuilt_site",
    "static_export_fingerprint",
    "static_file_inventory",
    "validate_static_export",
    "validate_published_site_budget",
    "write_prebuilt_manifest",
]
