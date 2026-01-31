#!/usr/bin/env python3
"""Scaffold a new plugin with tests and docs."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import textwrap
from typing import List

PLUGIN_TEMPLATE = textwrap.dedent(
    '''\
    # -*- coding: utf-8 -*-
    """{class_name} plugin."""

    from __future__ import annotations

    import numpy as np

    from waveform_analysis.core.plugins.core.base import Option, Plugin


    class {class_name}(Plugin):
        """{description}"""

        provides = "{provides}"
        depends_on = {depends_on}
        version = "0.1.0"
        description = "{description}"

        options = {{
            "threshold": Option(
                default=0.0,
                type=float,
                help="Min amplitude threshold for demo output.",
                track=True,
            ),
        }}

        output_dtype = np.dtype([
            ("channel", "i2"),
            ("value", "f4"),
        ])

        def compute(self, context, run_id, **kwargs):
    {compute_block}
    '''
)

TEST_TEMPLATE = textwrap.dedent(
    '''\
    # -*- coding: utf-8 -*-
    """Tests for {class_name}."""

    from __future__ import annotations

    from waveform_analysis.testing.fixtures import make_tiny_context

    from waveform_analysis.core.plugins.custom.{module_name} import {class_name}


    def test_contract(tmp_path):
        run_id = "run_001"
        ctx = make_tiny_context(tmp_path / "storage", run_id=run_id)
        ctx.register({class_name}())

        data = ctx.get_data(run_id, "{provides}")

        # TODO: adjust required fields for your plugin's output_dtype
        required_fields = {{"channel", "value"}}
        assert data.dtype == {class_name}.output_dtype
        assert required_fields.issubset(set(data.dtype.names or ()))


    def test_cache_invalidation(tmp_path):
        run_id = "run_001"
        ctx = make_tiny_context(tmp_path / "storage", run_id=run_id)
        ctx.register({class_name}())

        key1 = ctx.key_for(run_id, "{provides}")

        # Config change should update lineage hash
        ctx.set_config({{"threshold": 1.0}}, plugin_name="{provides}")
        key2 = ctx.key_for(run_id, "{provides}")
        assert key1 != key2

        # Version change should update lineage hash
        class {class_name}V2({class_name}):
            version = "0.1.1"

        ctx.register({class_name}V2(), allow_override=True)
        key3 = ctx.key_for(run_id, "{provides}")
        assert key2 != key3
    '''
)

DOC_TEMPLATE = textwrap.dedent(
    """\
    # {class_name}

    ## 概览

    - **提供数据**: `{provides}`
    - **依赖**: {depends_on_human}
    - **版本**: 0.1.0

    ## 配置

    | 参数 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `threshold` | `float` | `0.0` | 输出阈值（示例） |

    ## 输出

    `output_dtype`:

    - `channel`: `i2`
    - `value`: `f4`

    ## 使用示例

    ```python
    from waveform_analysis.core.context import Context
    from waveform_analysis.core.plugins.custom.{module_name} import {class_name}

    ctx = Context(storage_dir="./cache")
    ctx.register({class_name}())

    ctx.set_config({{"threshold": 1.0}}, plugin_name="{provides}")

    data = ctx.get_data("run_001", "{provides}")
    print(data)
    ```

    ## 测试建议

    - `test_contract`: 校验 dtype / 字段 / 关键统计
    - `test_cache_invalidation`: 版本或配置变更时 cache key 应更新
    """
)


def to_snake(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name)
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower().strip("_")


def parse_depends(value: str) -> List[str]:
    if not value:
        return []
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


def ensure_init(package_dir: Path) -> None:
    init_path = package_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            '# -*- coding: utf-8 -*-\n"""Custom plugins package."""\n',
            encoding="utf-8",
        )


def render_plugin(
    class_name: str,
    provides: str,
    depends_on: List[str],
    description: str,
) -> str:
    if depends_on:
        primary = depends_on[0]
        block = textwrap.dedent(
            """\
            records = context.get_data(run_id, {primary!r})
            # TODO: replace the logic with your real computation
            out = np.zeros(len(records), dtype=self.output_dtype)
            for idx, ch_records in enumerate(records):
                out[\"channel\"][idx] = idx
                if len(ch_records):
                    out[\"value\"][idx] = float(np.max(ch_records[\"wave\"]))
            return out
            """
        ).format(primary=primary)
    else:
        block = textwrap.dedent(
            """\
            # TODO: replace the logic with your real computation
            return np.zeros(1, dtype=self.output_dtype)
            """
        )

    compute_block = textwrap.indent(block, " " * 8).rstrip()

    return PLUGIN_TEMPLATE.format(
        class_name=class_name,
        provides=provides,
        depends_on=repr(depends_on),
        description=description,
        compute_block=compute_block,
    )


def render_tests(class_name: str, module_name: str, provides: str) -> str:
    return TEST_TEMPLATE.format(
        class_name=class_name,
        module_name=module_name,
        provides=provides,
    )


def render_doc(class_name: str, module_name: str, provides: str, depends_on: List[str]) -> str:
    if depends_on:
        depends_on_human = ", ".join(f"`{name}`" for name in depends_on)
    else:
        depends_on_human = "无"

    return DOC_TEMPLATE.format(
        class_name=class_name,
        module_name=module_name,
        provides=provides,
        depends_on_human=depends_on_human,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a plugin + tests + docs.")
    parser.add_argument("class_name", help="Plugin class name, e.g. MyPlugin")
    parser.add_argument("--provides", help="Data name provided by the plugin")
    parser.add_argument(
        "--depends-on",
        default="st_waveforms",
        help="Comma-separated dependency names (default: st_waveforms). Use empty string for none.",
    )
    parser.add_argument(
        "--plugins-dir",
        default="waveform_analysis/core/plugins/custom",
        help="Directory for plugin module",
    )
    parser.add_argument(
        "--tests-dir",
        default="tests/plugins",
        help="Directory for tests",
    )
    parser.add_argument(
        "--docs-dir",
        default="docs/plugins/custom",
        help="Directory for docs",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    args = parser.parse_args()

    class_name = args.class_name.strip()
    if not class_name:
        raise SystemExit("class_name is required")

    base_name = class_name[:-6] if class_name.endswith("Plugin") else class_name
    module_name = to_snake(base_name)
    provides = args.provides or to_snake(base_name)
    depends_on = parse_depends(args.depends_on)
    description = f"{class_name} plugin scaffold."

    plugins_dir = Path(args.plugins_dir)
    tests_dir = Path(args.tests_dir)
    docs_dir = Path(args.docs_dir)

    plugins_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    ensure_init(plugins_dir)

    plugin_path = plugins_dir / f"{module_name}.py"
    test_path = tests_dir / f"test_{module_name}.py"
    doc_path = docs_dir / f"{module_name}.md"

    for path in (plugin_path, test_path, doc_path):
        if path.exists() and not args.force:
            raise SystemExit(f"File exists: {path}. Use --force to overwrite.")

    plugin_content = render_plugin(class_name, provides, depends_on, description)
    test_content = render_tests(class_name, module_name, provides)
    doc_content = render_doc(class_name, module_name, provides, depends_on)

    plugin_path.write_text(plugin_content, encoding="utf-8")
    test_path.write_text(test_content, encoding="utf-8")
    doc_path.write_text(doc_content, encoding="utf-8")

    print("Scaffold created:")
    print(f"- {plugin_path}")
    print(f"- {test_path}")
    print(f"- {doc_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
