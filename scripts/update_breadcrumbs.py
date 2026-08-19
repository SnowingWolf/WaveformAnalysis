#!/usr/bin/env python3
"""
自动更新文档面包屑导航的脚本

用法:
    python scripts/update_breadcrumbs.py [--dry-run]

功能:
    - 根据文件路径自动生成面包屑
    - 支持预览模式 (--dry-run)
    - 自动识别目录层级
"""

import argparse
from pathlib import Path
import re

# 目录名称到显示名称的映射
DIR_NAMES = {
    "docs": "文档中心",
    "user-guide": "用户指南",
    "developer-guide": "开发者指南",
    "development": "开发者指南",
    "context": "Context 功能",
    "plugin": "插件功能",
    "plugins": "插件详解",
    "utils": "工具函数",
    "data-processing": "数据处理",
    "architecture": "架构设计",
    "plugin-development": "插件开发",
    "api": "API 参考",
    "cli": "命令行工具",
    "contributing": "开发规范",
    "updates": "更新记录",
    "features": "功能特性",
    "advanced": "高级功能",
}

# 文件名到标题的映射（可选，如果不在这里会从文件内容提取）
FILE_TITLES = {
    "DEPENDENCY_ANALYSIS_GUIDE.md": "依赖分析",
    "LINEAGE_VISUALIZATION.md": "血缘图预览",
    "SIGNAL_PROCESSING_PLUGINS.md": "信号处理插件",
    "STREAMING_PLUGINS_GUIDE.md": "流式处理插件",
    "STRAX_PLUGINS_ADAPTER.md": "Strax 适配器",
    "CACHE.md": "缓存系统",
    "EXECUTOR_MANAGER_GUIDE.md": "执行器管理",
    "PROGRESS_TRACKING_GUIDE.md": "进度追踪",
    "IO_CSV_HEADER_HANDLING.md": "CSV 处理",
    "ARCHITECTURE.md": "系统架构",
    "CONTEXT_PROCESSOR_WORKFLOW.md": "工作流程",
    "PROJECT_STRUCTURE.md": "项目结构",
    "plugin_guide.md": "插件开发完整指南",
    "api_reference.md": "API 参考文档",
    "config_reference.md": "配置参考",
    "IMPORT_STYLE_GUIDE.md": "导入风格指南",
}


def get_title_from_file(filepath: Path) -> str:
    """从文件内容提取标题"""
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                # 跳过面包屑行
                if line.startswith("**导航**"):
                    continue
                # 跳过空行和分隔线
                if line.strip() == "" or line.strip() == "---":
                    continue
                # 找到第一个标题
                match = re.match(r"^#\s+(.+)$", line.strip())
                if match:
                    return match.group(1)
    except Exception:
        pass
    return filepath.stem


def generate_breadcrumb(filepath: Path, docs_root: Path) -> str:
    """根据文件路径生成面包屑"""
    rel_path = filepath.relative_to(docs_root)
    parts = list(rel_path.parts)

    # 移除文件名，只保留目录
    filename = parts.pop()

    # 如果是 README.md，不需要面包屑中的最后一级
    is_readme = filename.lower() == "readme.md"

    # 构建面包屑路径
    breadcrumb_parts = []
    current_depth = len(parts)

    # 添加文档中心
    relative_to_root = "../" * current_depth
    breadcrumb_parts.append(f"[文档中心]({relative_to_root}README.md)")

    # 添加中间目录
    for i, part in enumerate(parts):
        dir_name = DIR_NAMES.get(part, part)
        is_last_dir = i == len(parts) - 1

        # 如果是 README 且是最后一个目录，不加链接
        if is_readme and is_last_dir:
            breadcrumb_parts.append(dir_name)
        else:
            depth_from_here = current_depth - i - 1
            if depth_from_here > 0:
                path = "../" * depth_from_here + "README.md"
            else:
                path = "README.md"
            breadcrumb_parts.append(f"[{dir_name}]({path})")

    # 如果不是 README，添加当前文件标题
    if not is_readme:
        title = FILE_TITLES.get(filename) or get_title_from_file(filepath)
        breadcrumb_parts.append(title)

    return "**导航**: " + " > ".join(breadcrumb_parts)


def update_file_breadcrumb(filepath: Path, docs_root: Path, dry_run: bool = False) -> bool:
    """更新单个文件的面包屑"""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return False

    new_breadcrumb = generate_breadcrumb(filepath, docs_root)

    # 检查是否有现有面包屑
    breadcrumb_pattern = r"^\*\*导航\*\*:.*$"

    lines = content.split("\n")
    updated = False

    for i, line in enumerate(lines):
        if re.match(breadcrumb_pattern, line):
            if line != new_breadcrumb:
                if dry_run:
                    print(f"  旧: {line}")
                    print(f"  新: {new_breadcrumb}")
                else:
                    lines[i] = new_breadcrumb
                updated = True
            break
    else:
        # 没有找到面包屑，在开头添加
        if dry_run:
            print(f"  添加: {new_breadcrumb}")
        else:
            lines.insert(0, new_breadcrumb)
            lines.insert(1, "")
        updated = True

    if updated and not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    return updated


def main():
    parser = argparse.ArgumentParser(description="自动更新文档面包屑导航")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际修改文件")
    parser.add_argument("--path", type=str, default="docs", help="文档根目录")
    args = parser.parse_args()

    # 找到项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    docs_root = project_root / args.path

    if not docs_root.exists():
        print(f"❌ 文档目录不存在: {docs_root}")
        return 1

    print(f"📁 文档根目录: {docs_root}")
    print(f"🔍 模式: {'预览' if args.dry_run else '更新'}")
    print()

    # 遍历所有 markdown 文件
    updated_count = 0
    skipped_count = 0

    for md_file in docs_root.rglob("*.md"):
        rel_path = md_file.relative_to(docs_root)

        # 跳过根目录的 README
        if str(rel_path) == "README.md":
            continue

        # 跳过 updates 目录（通常不需要面包屑）
        if "updates" in rel_path.parts:
            skipped_count += 1
            continue

        print(f"📄 {rel_path}")
        if update_file_breadcrumb(md_file, docs_root, args.dry_run):
            updated_count += 1
        else:
            print("  ✓ 无需更新")

    print()
    print(f"✅ 完成: {updated_count} 个文件{'需要' if args.dry_run else '已'}更新")
    if skipped_count:
        print(f"⏭️  跳过: {skipped_count} 个文件")

    return 0


if __name__ == "__main__":
    exit(main())
