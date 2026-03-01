#!/usr/bin/env python
"""
CI 用插件文档检查脚本

用于 CI 环境中检查插件文档覆盖率和一致性。

用法:
    python scripts/check_plugin_docs.py [--strict] [--generate]

选项:
    --strict    严格模式，也检查 spec 质量
    --generate  先生成文档再检查
"""

import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="检查插件文档覆盖率")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--generate", action="store_true", help="先生成文档")
    args = parser.parse_args()

    # 确定项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    docs_dir = project_root / "docs"
    auto_docs_dir = docs_dir / "plugins" / "reference" / "builtin" / "auto"

    # 如果需要，先生成文档
    if args.generate:
        print("📝 生成插件文档...")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "waveform_analysis.utils.cli_docs",
                "generate",
                "plugins-auto",
                "-o",
                str(auto_docs_dir),
            ],
            cwd=project_root,
        )
        if result.returncode != 0:
            print("❌ 文档生成失败")
            return 1
        print()

    # 检查覆盖率
    print("🔍 检查文档覆盖率...")
    cmd = [
        sys.executable,
        "-m",
        "waveform_analysis.utils.cli_docs",
        "check",
        "coverage",
        "-d",
        str(docs_dir),
    ]
    if args.strict:
        cmd.append("--strict")

    result = subprocess.run(cmd, cwd=project_root)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
