#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Doc Anchor 检查脚本

检查代码中的 # DOC: 注释是否有效：
1. 文档文件是否存在（Fail）
2. 锚点是否存在（Warn）
3. PR 中代码变更是否需要同步文档（Warn）

使用方法:
    python scripts/check_doc_anchors.py
    python scripts/check_doc_anchors.py --check-sync --base origin/main
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple


class DocAnchor(NamedTuple):
    """文档锚点信息"""
    file_path: str
    line_num: int
    doc_path: str
    anchor: Optional[str]
    raw_line: str


class Issue(NamedTuple):
    """检查问题"""
    file_path: str
    line_num: int
    severity: str
    message: str
    raw_line: str


# DOC 注释正则表达式
# 支持格式 (示例见 DOC_ANCHOR_GUIDE.md):
#   - 无锚点: # DOC: docs/xxx.md
#   - 有锚点: # DOC: docs/xxx.md#anchor
DOC_PATTERN = re.compile(
    r'#\s*DOC:\s*(?P<path>docs/[^\s#]+)(?:#(?P<anchor>[^\s]+))?'
)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def find_doc_anchors(file_path: Path) -> List[DocAnchor]:
    """扫描文件中的 DOC 注释

    Args:
        file_path: Python 文件路径

    Returns:
        DocAnchor 列表
    """
    anchors = []
    try:
        content = file_path.read_text(encoding='utf-8')
        for line_num, line in enumerate(content.split('\n'), 1):
            match = DOC_PATTERN.search(line)
            if match:
                anchors.append(DocAnchor(
                    file_path=str(file_path),
                    line_num=line_num,
                    doc_path=match.group('path'),
                    anchor=match.group('anchor'),
                    raw_line=line.strip(),
                ))
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)
    return anchors


def check_doc_exists(doc_path: str) -> bool:
    """检查文档文件是否存在

    Args:
        doc_path: 相对于项目根目录的文档路径

    Returns:
        文档是否存在
    """
    full_path = PROJECT_ROOT / doc_path
    return full_path.exists() and full_path.is_file()


def check_anchor_exists(doc_path: str, anchor: str) -> bool:
    """检查文档中的锚点是否存在

    Markdown 锚点规则：
    - 标题会自动生成锚点
    - 锚点是标题的小写形式，空格替换为 -，移除特殊字符

    Args:
        doc_path: 文档路径
        anchor: 锚点名称

    Returns:
        锚点是否存在
    """
    full_path = PROJECT_ROOT / doc_path
    if not full_path.exists():
        return False

    try:
        content = full_path.read_text(encoding='utf-8')

        # 生成所有可能的锚点
        anchors = set()

        # 从标题生成锚点
        for line in content.split('\n'):
            if line.startswith('#'):
                # 提取标题文本
                title = re.sub(r'^#+\s*', '', line).strip()
                # 生成锚点：小写，空格替换为 -，移除特殊字符
                generated_anchor = title.lower()
                generated_anchor = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', generated_anchor)
                generated_anchor = re.sub(r'\s+', '-', generated_anchor)
                generated_anchor = re.sub(r'-+', '-', generated_anchor)
                generated_anchor = generated_anchor.strip('-')
                anchors.add(generated_anchor)

                # 也添加原始标题（某些 Markdown 渲染器保留大小写）
                anchors.add(title.replace(' ', '-'))

        # 检查显式定义的锚点 <a name="..."> 或 <a id="...">
        explicit_anchors = re.findall(r'<a\s+(?:name|id)=["\']([^"\']+)["\']', content)
        anchors.update(explicit_anchors)

        # 检查锚点是否存在（不区分大小写比较）
        anchor_lower = anchor.lower()
        return any(a.lower() == anchor_lower for a in anchors)

    except Exception:
        return False


def validate_anchors(anchors: List[DocAnchor]) -> List[Issue]:
    """验证所有 DOC 锚点

    Args:
        anchors: DocAnchor 列表

    Returns:
        Issue 列表
    """
    issues = []

    for anchor in anchors:
        # 检查文档文件是否存在
        if not check_doc_exists(anchor.doc_path):
            issues.append(Issue(
                file_path=anchor.file_path,
                line_num=anchor.line_num,
                severity='error',
                message=f"文档文件不存在: {anchor.doc_path}",
                raw_line=anchor.raw_line,
            ))
            continue

        # 检查锚点是否存在
        if anchor.anchor and not check_anchor_exists(anchor.doc_path, anchor.anchor):
            issues.append(Issue(
                file_path=anchor.file_path,
                line_num=anchor.line_num,
                severity='warning',
                message=f"锚点不存在: {anchor.doc_path}#{anchor.anchor}",
                raw_line=anchor.raw_line,
            ))

    return issues


def get_changed_files(base: str) -> Tuple[Set[str], Set[str]]:
    """获取相对于 base 的变更文件

    Args:
        base: Git 基准引用（如 origin/main, HEAD~1）

    Returns:
        (changed_code_files, changed_doc_files) 元组
    """
    try:
        # 获取变更的代码文件
        result = subprocess.run(
            ['git', 'diff', '--name-only', base, '--',
             'waveform_analysis/', '*.py', ':!docs/', ':!tests/'],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        code_files = set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()

        # 获取变更的文档文件
        result = subprocess.run(
            ['git', 'diff', '--name-only', base, '--', 'docs/'],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        doc_files = set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()

        return code_files, doc_files
    except Exception as e:
        print(f"Warning: Failed to get git diff: {e}", file=sys.stderr)
        return set(), set()


def check_sync(base: str, anchors: List[DocAnchor]) -> List[Issue]:
    """检查代码变更是否需要同步文档

    Args:
        base: Git 基准引用
        anchors: 所有 DOC 锚点

    Returns:
        Issue 列表
    """
    issues = []
    changed_code, changed_docs = get_changed_files(base)

    if not changed_code:
        return issues

    # 构建代码文件到文档的映射
    code_to_docs: Dict[str, Set[str]] = {}
    for anchor in anchors:
        # 转换为相对路径
        rel_path = os.path.relpath(anchor.file_path, PROJECT_ROOT)
        if rel_path not in code_to_docs:
            code_to_docs[rel_path] = set()
        code_to_docs[rel_path].add(anchor.doc_path)

    # 检查变更的代码文件是否有对应的文档变更
    for code_file in changed_code:
        if code_file in code_to_docs:
            related_docs = code_to_docs[code_file]
            missing_docs = related_docs - changed_docs
            if missing_docs:
                issues.append(Issue(
                    file_path=code_file,
                    line_num=0,
                    severity='warning',
                    message=f"代码已变更，但关联文档未更新: {', '.join(sorted(missing_docs))}",
                    raw_line='',
                ))

    return issues


def scan_all_files() -> List[DocAnchor]:
    """扫描所有 Python 文件中的 DOC 注释

    Returns:
        所有 DocAnchor 列表
    """
    all_anchors = []
    # 跳过本脚本自身
    self_path = Path(__file__).resolve()

    # 扫描 waveform_analysis 目录
    wa_path = PROJECT_ROOT / 'waveform_analysis'
    if wa_path.exists():
        for py_file in wa_path.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
            all_anchors.extend(find_doc_anchors(py_file))

    # 扫描 scripts 目录
    scripts_path = PROJECT_ROOT / 'scripts'
    if scripts_path.exists():
        for py_file in scripts_path.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
            if py_file.resolve() == self_path:
                continue
            all_anchors.extend(find_doc_anchors(py_file))

    return all_anchors


def print_issues(issues: List[Issue]) -> Tuple[int, int]:
    """打印问题列表

    Args:
        issues: Issue 列表

    Returns:
        (error_count, warning_count) 元组
    """
    error_count = 0
    warning_count = 0

    # 按文件分组
    by_file: Dict[str, List[Issue]] = {}
    for issue in issues:
        if issue.file_path not in by_file:
            by_file[issue.file_path] = []
        by_file[issue.file_path].append(issue)

    for file_path, file_issues in sorted(by_file.items()):
        print(f"\n{file_path}:")
        for issue in file_issues:
            marker = "❌" if issue.severity == 'error' else "⚠️"
            if issue.severity == 'error':
                error_count += 1
            else:
                warning_count += 1

            if issue.line_num > 0:
                print(f"  {marker} Line {issue.line_num}: {issue.message}")
                if issue.raw_line:
                    print(f"     {issue.raw_line}")
            else:
                print(f"  {marker} {issue.message}")

    return error_count, warning_count


def print_summary(anchors: List[DocAnchor], error_count: int, warning_count: int):
    """打印摘要信息"""
    print(f"\n{'=' * 50}")
    print(f"Doc Anchor 检查摘要")
    print(f"{'=' * 50}")
    print(f"  扫描到的 DOC 注释: {len(anchors)}")
    print(f"  ❌ 错误: {error_count}")
    print(f"  ⚠️  警告: {warning_count}")

    if error_count == 0 and warning_count == 0:
        print(f"\n✓ 所有 Doc Anchor 检查通过")
    else:
        print(f"\n提示: 错误必须修复，警告建议处理")


def main():
    parser = argparse.ArgumentParser(description='检查代码中的 DOC 注释')
    parser.add_argument(
        '--check-sync', action='store_true',
        help='检查代码变更是否需要同步文档'
    )
    parser.add_argument(
        '--base', default='HEAD',
        help='Git 基准引用（默认 HEAD）'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='显示详细信息'
    )
    args = parser.parse_args()

    print("Doc Anchor 检查")
    print("=" * 50)

    # 扫描所有 DOC 注释
    anchors = scan_all_files()

    if args.verbose:
        print(f"\n找到 {len(anchors)} 个 DOC 注释:")
        for anchor in anchors:
            rel_path = os.path.relpath(anchor.file_path, PROJECT_ROOT)
            if anchor.anchor:
                print(f"  {rel_path}:{anchor.line_num} -> {anchor.doc_path}#{anchor.anchor}")
            else:
                print(f"  {rel_path}:{anchor.line_num} -> {anchor.doc_path}")

    # 验证锚点
    issues = validate_anchors(anchors)

    # 检查同步（如果启用）
    if args.check_sync:
        print(f"\n检查代码与文档同步 (base: {args.base})...")
        sync_issues = check_sync(args.base, anchors)
        issues.extend(sync_issues)

    # 打印问题
    if issues:
        print(f"\n发现问题:")
        error_count, warning_count = print_issues(issues)
    else:
        error_count, warning_count = 0, 0

    # 打印摘要
    print_summary(anchors, error_count, warning_count)

    # 返回退出码
    if error_count > 0:
        return 1
    elif warning_count > 0:
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
