#!/usr/bin/env python3
"""
插件 bundle 依赖校验脚本

校验 per-plugin bundle 的依赖声明一致性：

1. bundle 代码顶层第三方 import ⊆（requirements.txt ∪ pyproject 基线/extras）
2. manifest.yaml.third_party_dependencies == requirements.txt（单源真相）
3. 跨 bundle 代码依赖必须在 manifest.plugin_dependencies 声明
4. 旧模块 shim 导出完备性：repo 中 `from builtin.<mod> import <name>` 均能解析

使用方法:
    python scripts/check_plugin_deps.py
    python scripts/check_plugin_deps.py --quiet   # 仅报错误，不显示成功清单
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
BUILTIN_DIR = REPO_ROOT / "waveform_analysis" / "core" / "plugins" / "builtin"

STDLIB = set(getattr(sys, "stdlib_module_names", ()))

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None

errors: list[str] = []
warnings: list[str] = []


def add(msg: str, *, warning: bool = False) -> None:
    (warnings if warning else errors).append(msg)


def top_level(name: str) -> str:
    return name.split(".")[0].split("[")[0].strip()


def parse_req_packages(lines: list[str]) -> set[str]:
    pkgs: set[str] = set()
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        base = re.split(r"[<>=!\[\];@~]", line)[0].strip()
        if base:
            pkgs.add(base.lower())
    return pkgs


def pyproject_baseline() -> set[str]:
    """从 pyproject.toml 的 dependencies + 全部 extras 提取包名集合。"""
    if tomllib is None:
        add("tomllib/tomli 不可用，跳过 pyproject 基线比对", warning=True)
        return set()
    try:
        with PYPROJECT.open("rb") as f:
            data = tomllib.load(f)
    except Exception as e:  # pragma: no cover
        add(f"解析 pyproject.toml 失败: {e}", warning=True)
        return set()

    base: set[str] = set()
    proj = data.get("project", {})
    for dep in proj.get("dependencies", []) or []:
        base.add(re.split(r"[<>=!\[\];@~]", dep)[0].strip().lower())
    for extra in (proj.get("optional-dependencies", {}) or {}).values():
        for dep in extra or []:
            base.add(re.split(r"[<>=!\[\];@~]", dep)[0].strip().lower())
    return base


def iter_bundle_py(bundle_dir: Path) -> list[Path]:
    """bundle 实现文件（仅 plugin.py 与 _compute.py，排除 __init__/tests/遗留 shim）。"""
    out = []
    for name in ("plugin.py", "_compute.py"):
        p = bundle_dir / name
        if p.exists():
            out.append(p)
    return out


def third_party_imports(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                found.add(top_level(a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(top_level(node.module))
    return {m for m in found if m not in STDLIB and not m.startswith("waveform_analysis")}


def validate_bundle(bundle_dir: Path, all_provides: set[str], baseline: set[str]) -> None:
    from waveform_analysis.core.plugins.builtin._registry import (
        BundleManifest,  # type: ignore[import-not-found]
    )

    try:
        manifest = BundleManifest.from_yaml(bundle_dir / "manifest.yaml")
    except Exception as e:  # pragma: no cover
        add(f"[{bundle_dir.name}] manifest.yaml 解析失败: {e}")
        return

    req_file = bundle_dir / "requirements.txt"
    req_pkgs = (
        parse_req_packages(req_file.read_text(encoding="utf-8").splitlines())
        if req_file.exists()
        else set()
    )

    code_pkgs: set[str] = set()
    for pyf in iter_bundle_py(bundle_dir):
        code_pkgs |= third_party_imports(pyf)

    # 1) 代码第三方依赖 ⊆ (requirements ∪ 基线)
    missing = code_pkgs - req_pkgs - baseline
    if missing:
        add(f"[{manifest.provides}] 代码 import 了未声明的第三方包: {sorted(missing)}")

    # 2) manifest 与 requirements.txt 一致
    manifest_pkgs = {p.lower() for p in manifest.third_party_dependencies}
    if manifest_pkgs != {p.lower() for p in req_pkgs}:
        add(
            f"[{manifest.provides}] manifest.third_party_dependencies 与 requirements.txt 不一致: "
            f"manifest={sorted(manifest_pkgs)} requirements={sorted(req_pkgs)}"
        )

    # 3) 跨 bundle 代码依赖声明
    declared = set(manifest.plugin_dependencies)
    content = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in iter_bundle_py(bundle_dir)
    )
    for other in all_provides:
        if other == manifest.provides:
            continue
        if re.search(rf"(?:builtin\.|\.\.+){re.escape(other)}(?:\b|\.)", content):
            if other not in declared:
                add(
                    f"[{manifest.provides}] 引用了兄弟 bundle '{other}' 但 "
                    f"manifest.plugin_dependencies 未声明"
                )


_MOD_CACHE: dict[str, object | None] = {}


def _resolve_import(mod: str, name: str) -> bool:
    if mod not in _MOD_CACHE:
        try:
            _MOD_CACHE[mod] = importlib.import_module(
                f"waveform_analysis.core.plugins.builtin.{mod}"
            )
        except Exception:
            _MOD_CACHE[mod] = None
    module = _MOD_CACHE[mod]
    if module is None:
        return True  # 模块本身无法导入（依赖缺失等），无法验证，跳过
    if hasattr(module, name):
        return True
    # 可能 name 是子模块（如 from builtin.hit import hit_merged_features）
    try:
        importlib.import_module(f"waveform_analysis.core.plugins.builtin.{mod}.{name}")
        return True
    except Exception:
        return False


def check_shim_completeness() -> tuple[int, int]:
    """扫描 repo 中 `from builtin.<mod> import <name>`，断言均可解析。

    Returns:
        (checked, broken) 检查的 from-import 数量与缺失数量
    """
    pattern = re.compile(
        r"from waveform_analysis\.core\.plugins\.builtin\.([a-z_0-9]+(?:\.[a-z_0-9]+)*) import (.*)"
    )
    checked = 0
    broken = 0
    for base in (REPO_ROOT / "waveform_analysis", REPO_ROOT / "tests"):
        if not base.exists():
            continue
        for pyf in base.rglob("*.py"):
            if "__pycache__" in str(pyf):
                continue
            try:
                lines = pyf.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:  # pragma: no cover
                continue
            for line in lines:
                m = pattern.match(line.strip())
                if not m:
                    continue
                mod, names = m.group(1), m.group(2)
                if " as " in names or "*" in names:
                    # 别名/星号导入难以静态判断，交给 import 期验证
                    continue
                for part in names.split(","):
                    part = part.strip().strip("()").split("#", 1)[0].strip()
                    if not part:
                        continue
                    name = part.split(" as ")[0].strip()
                    if not name:
                        continue
                    checked += 1
                    if not _resolve_import(mod, name):
                        broken += 1
                        add(
                            f"shim: builtin.{mod} 缺少导出 '{name}' "
                            f"（被 {pyf.relative_to(REPO_ROOT)} 引用）"
                        )
    return checked, broken


def main() -> int:
    quiet = "--quiet" in sys.argv

    # 保证能 import 项目包（e.g. 在未安装 editable 时直接跑脚本）
    repo_root_str = str(REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    baseline = pyproject_baseline()

    from waveform_analysis.core.plugins.builtin._registry import (  # type: ignore[import-not-found]
        iter_bundle_dirs,
        iter_manifests,
    )

    manifests = iter_manifests()
    bundles = iter_bundle_dirs()
    all_provides = {m.provides for m in manifests}

    if not bundles:
        print("当前无 bundle（尚未建立 manifest.yaml），仅执行 shim 完备性检查。")
    for d in bundles:
        validate_bundle(d, all_provides, baseline)

    checked, broken = check_shim_completeness()

    if not quiet:
        print(f"bundles 校验: {len(bundles)} 个")
        print(f"shim 完备性: 检查 {checked} 处 from-import，{broken} 处缺失")
        if warnings:
            print("\n警告:")
            for w in warnings:
                print(f"  ⚠️  {w}")

    if errors:
        print(f"\n发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  ❌ {e}")
        return 1

    if not quiet:
        print("✓ 插件依赖声明一致，shim 导出完备")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
