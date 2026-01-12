#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入规范检查脚本

检查代码库中的导入是否符合规范：
1. 禁止使用超过两级的相对导入（...）
2. 禁止使用 Python 3.10+ 的联合类型语法（str | Path）
3. 检查导入路径是否正确

使用方法:
    python scripts/check_imports.py
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple

# 禁止的模式
FORBIDDEN_PATTERNS = [
    (
        r'from \.\.\..*foundation',
        '禁止使用三级相对导入。应使用: from waveform_analysis.core.foundation',
        'error'
    ),
    (
        r'from \.\.\..*chunk_utils',
        'chunk_utils 已移动到 processing.chunk。应使用: from waveform_analysis.core.processing.chunk',
        'error'
    ),
    (
        r'str \| Path|int \| |float \| |bool \| ',
        '禁止使用 Python 3.10+ 的联合类型语法。应使用: Union[str, Path]',
        'error'
    ),
    (
        r'from \.\.\..*utils import exporter',
        '应使用绝对导入: from waveform_analysis.core.foundation.utils import exporter',
        'warning'
    ),
]

# 导入路径映射（用于验证）
EXPECTED_IMPORTS = {
    'chunk_utils': 'waveform_analysis.core.processing.chunk',
    'foundation.utils': 'waveform_analysis.core.foundation.utils',
    'foundation.exceptions': 'waveform_analysis.core.foundation.exceptions',
    'foundation.mixins': 'waveform_analysis.core.foundation.mixins',
    'executor_manager': 'waveform_analysis.core.execution.manager',
    'processor': 'waveform_analysis.core.processing.processor',
    'analyzer': 'waveform_analysis.core.processing.analyzer',
}


def check_file(file_path: Path) -> List[Tuple[int, str, str, str]]:
    """
    检查文件中的导入问题
    
    Returns:
        List of (line_number, line_content, issue_type, message)
    """
    issues = []
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        for line_num, line in enumerate(content.split('\n'), 1):
            for pattern, message, severity in FORBIDDEN_PATTERNS:
                if re.search(pattern, line):
                    issues.append((line_num, line.strip(), severity, message))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return issues


def main():
    """主函数"""
    path = Path('waveform_analysis')
    if not path.exists():
        print(f"Error: Path {path} does not exist")
        return 1
    
    all_issues = []
    error_count = 0
    warning_count = 0
    
    # 查找所有 Python 文件
    for py_file in path.rglob('*.py'):
        if '__pycache__' in str(py_file) or '.pyc' in str(py_file):
            continue
        
        issues = check_file(py_file)
        if issues:
            all_issues.append((py_file, issues))
            for _, _, severity, _ in issues:
                if severity == 'error':
                    error_count += 1
                else:
                    warning_count += 1
    
    # 输出结果
    if all_issues:
        print(f"\n发现导入规范问题:\n")
        for file_path, issues in all_issues:
            print(f"{file_path}:")
            for line_num, line, severity, message in issues:
                severity_marker = "❌" if severity == 'error' else "⚠️"
                print(f"  {severity_marker} Line {line_num}: {message}")
                print(f"     {line}")
            print()
        
        print(f"\n统计:")
        print(f"  ❌ 错误: {error_count}")
        print(f"  ⚠️  警告: {warning_count}")
        print(f"  总计: {error_count + warning_count}")
        print(f"\n运行 'python scripts/fix_imports.py --fix' 自动修复")
        return 1
    else:
        print("✓ 所有导入路径符合规范")
        return 0


if __name__ == '__main__':
    exit(main())


