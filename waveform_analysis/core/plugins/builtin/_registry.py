"""
builtin._registry - 插件 bundle 注册表

扫描 ``builtin/`` 下各 per-plugin bundle 的 ``manifest.yaml``，建立 provides→bundle 映射，
为文档发现、契约测试、装配层提供统一的插件枚举入口。

设计说明：
- 每个 provides 一个目录（flat bundle），内含 ``manifest.yaml`` 声明元数据。
- 本注册表只解析 manifest.yaml，**不 import 插件类**，因此即使某 bundle 的第三方
  依赖缺失也能安全枚举（避免在扫描阶段触发 ImportError）。
- 尚未迁移为 bundle 的插件（无 manifest）不会被列出；迁移推进后逐步补齐。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BUILTIN_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class BundleManifest:
    """单个插件 bundle 的机器可读声明。

    三个依赖字段刻意分列：
    - ``depends_on``: 数据依赖（插件间数据流）
    - ``third_party_dependencies``: 第三方 Python 包
    - ``plugin_dependencies``: 跨 bundle 代码耦合（import 了兄弟 bundle 的实现）
    """

    provides: str
    plugin_class: str
    version: str = "0.0.0"
    depends_on: tuple[str, ...] = ()
    third_party_dependencies: tuple[str, ...] = ()
    plugin_dependencies: tuple[str, ...] = ()
    category: str = ""
    manifest_path: str = ""

    @classmethod
    def from_yaml(cls, path: Path) -> BundleManifest:
        data = _load_yaml(path)
        return cls(
            provides=data.get("provides", ""),
            plugin_class=data.get("plugin_class", ""),
            version=data.get("version", "0.0.0"),
            depends_on=tuple(data.get("depends_on") or ()),
            third_party_dependencies=tuple(data.get("third_party_dependencies") or ()),
            plugin_dependencies=tuple(data.get("plugin_dependencies") or ()),
            category=data.get("category", ""),
            manifest_path=str(path),
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def iter_bundle_dirs() -> list[Path]:
    """返回含 ``manifest.yaml`` 的 bundle 目录（按名称排序）。"""
    return sorted(
        (p for p in BUILTIN_DIR.iterdir() if p.is_dir() and (p / "manifest.yaml").is_file()),
        key=lambda p: p.name,
    )


def iter_manifests() -> list[BundleManifest]:
    """扫描全部 bundle manifest.yaml，返回 :class:`BundleManifest` 列表。

    单个 manifest 解析失败不会阻断整体枚举（记录为跳过）。
    """
    out: list[BundleManifest] = []
    for d in iter_bundle_dirs():
        try:
            out.append(BundleManifest.from_yaml(d / "manifest.yaml"))
        except Exception:
            continue
    return out


def get_bundle(provides: str) -> BundleManifest | None:
    """按 provides 查找 bundle manifest。"""
    for m in iter_manifests():
        if m.provides == provides:
            return m
    return None


def provides_index() -> dict[str, BundleManifest]:
    """provides → BundleManifest 映射。"""
    return {m.provides: m for m in iter_manifests()}
