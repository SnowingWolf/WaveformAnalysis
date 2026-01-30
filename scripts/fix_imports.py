#!/usr/bin/env python3
"""
自动修复导入路径脚本

使用方法:
    python scripts/fix_imports.py              # 检查并显示问题
    python scripts/fix_imports.py --fix        # 自动修复
    python scripts/fix_imports.py --check      # 只检查不修复
"""

import argparse
from pathlib import Path
import re
from typing import List, Tuple

# 导入路径映射表（旧路径 -> 新路径）
IMPORT_REPLACEMENTS: List[Tuple[str, str, str]] = [
    # (模式, 替换, 描述)
    # 相对导入 -> 绝对导入
    (
        r"from \.\.\..*foundation\.utils import",
        "from waveform_analysis.core.foundation.utils import",
        "相对导入 foundation.utils -> 绝对导入",
    ),
    (
        r"from \.\.\..*chunk_utils import",
        "from waveform_analysis.core.processing.chunk import",
        "chunk_utils 已移动到 processing.chunk",
    ),
    (
        r"from \.\.\..*utils import exporter",
        "from waveform_analysis.core.foundation.utils import exporter",
        "相对导入 utils.exporter -> 绝对导入",
    ),
    (
        r"from \.\.\..*foundation import",
        "from waveform_analysis.core.foundation import",
        "相对导入 foundation -> 绝对导入",
    ),
    # 类型注解（Python 3.8 兼容）
    (r"str \| Path", "Union[str, Path]", "str | Path -> Union[str, Path] (Python 3.8 兼容)"),
    (r"int \| float", "Union[int, float]", "int | float -> Union[int, float]"),
    (r"str \| None", "Optional[str]", "str | None -> Optional[str]"),
    (r"int \| None", "Optional[int]", "int | None -> Optional[int]"),
    (r"float \| None", "Optional[float]", "float | None -> Optional[float]"),
    (r"bool \| None", "Optional[bool]", "bool | None -> Optional[bool]"),
]

# 需要添加 Union 导入的文件模式
FILES_NEEDING_UNION = [
    "**/daq*.py",
    "**/cache.py",
]


def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    检查文件中的导入问题

    Returns:
        List of (line_number, line_content, issue_description)
    """
    issues = []
    try:
        content = file_path.read_text(encoding="utf-8")

        for line_num, line in enumerate(content.split("\n"), 1):
            for pattern, _replacement, description in IMPORT_REPLACEMENTS:
                if re.search(pattern, line):
                    issues.append((line_num, line.strip(), description))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return issues


def fix_file(file_path: Path, dry_run: bool = False) -> bool:
    """
    修复文件中的导入问题

    Returns:
        True if file was modified
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content

        # 应用所有替换
        for pattern, replacement, _description in IMPORT_REPLACEMENTS:
            content = re.sub(pattern, replacement, content)

        # 如果需要 Union，检查是否已导入
        if any(file_path.match(pattern) for pattern in FILES_NEEDING_UNION):
            if "Union[" in content and "from typing import" in content:
                if "Union" not in re.search(r"from typing import ([^)]+)", content).group(1):
                    # 添加 Union 到导入
                    content = re.sub(r"(from typing import [^)]+)", r"\1, Union", content, count=1)

        if content != original:
            if not dry_run:
                file_path.write_text(content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="检查和修复导入路径问题")
    parser.add_argument("--fix", action="store_true", help="自动修复问题")
    parser.add_argument("--check", action="store_true", help="只检查不修复")
    parser.add_argument("--path", type=str, default="waveform_analysis", help="要检查的路径")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path {path} does not exist")
        return 1

    all_issues = []
    fixed_files = []

    # 查找所有 Python 文件
    for py_file in path.rglob("*.py"):
        if "__pycache__" in str(py_file) or ".pyc" in str(py_file):
            continue

        if args.check or not args.fix:
            # 检查模式
            issues = check_file(py_file)
            if issues:
                all_issues.append((py_file, issues))
        else:
            # 修复模式
            if fix_file(py_file, dry_run=False):
                fixed_files.append(py_file)

    # 输出结果
    if args.check or not args.fix:
        if all_issues:
            print(f"\n发现 {len(all_issues)} 个文件有导入问题:\n")
            for file_path, issues in all_issues:
                print(f"{file_path}:")
                for line_num, line, description in issues:
                    print(f"  Line {line_num}: {description}")
                    print(f"    {line}")
                print()
            print(f"\n总共发现 {sum(len(issues) for _, issues in all_issues)} 个问题")
            print("运行 'python scripts/fix_imports.py --fix' 自动修复")
            return 1
        else:
            print("✓ 所有导入路径检查通过")
            return 0
    else:
        if fixed_files:
            print(f"\n✓ 修复了 {len(fixed_files)} 个文件:")
            for f in fixed_files:
                print(f"  - {f}")
            return 0
        else:
            print("✓ 没有需要修复的文件")
            return 0


if __name__ == "__main__":
    exit(main())
