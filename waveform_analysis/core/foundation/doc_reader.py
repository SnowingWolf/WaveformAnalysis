"""
文档读取器模块

从 docs/ 目录读取 Markdown 文件并转换为终端友好格式。
支持回退到内置内容。
"""

from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


# Help 主题到文档文件的映射
TOPIC_DOC_MAPPING: Dict[str, List[str]] = {
    "quickstart": [
        "user-guide/QUICKSTART_GUIDE.md",
    ],
    "config": [
        "features/context/CONFIGURATION.md",
    ],
    "plugins": [
        "features/plugin/README.md",
        "features/plugin/SIMPLE_PLUGIN_GUIDE.md",
        "features/plugin/SIGNAL_PROCESSING_PLUGINS.md",
    ],
    "performance": [
        "features/advanced/EXECUTOR_MANAGER_GUIDE.md",
        "features/advanced/CACHE.md",
        "features/advanced/PROGRESS_TRACKING_GUIDE.md",
    ],
    "examples": [
        "user-guide/EXAMPLES_GUIDE.md",
        "features/context/PREVIEW_EXECUTION.md",
        "features/context/LINEAGE_VISUALIZATION_GUIDE.md",
    ],
}


@export
def find_docs_root() -> Optional[Path]:
    """
    查找 docs/ 目录的位置

    搜索顺序:
    1. 当前工作目录下的 docs/
    2. 包安装目录的上级 docs/
    3. 从当前文件向上查找

    Returns:
        docs 目录路径，未找到返回 None
    """
    # 方法 1: 当前工作目录
    cwd_docs = Path.cwd() / "docs"
    if cwd_docs.is_dir() and (cwd_docs / "README.md").exists():
        return cwd_docs

    # 方法 2: 从当前模块向上查找
    current = Path(__file__).resolve()
    for _ in range(10):  # 最多向上 10 级
        current = current.parent
        docs_path = current / "docs"
        if docs_path.is_dir() and (docs_path / "README.md").exists():
            return docs_path
        if current == current.parent:  # 到达根目录
            break

    return None


@export
class MarkdownToTerminal:
    """Markdown 到终端格式转换器"""

    # 标题样式
    HEADER_STYLES = {
        1: ("╔", "═", "╗", "║", "╚", "═", "╝"),  # 双线框
        2: ("┌", "─", "┐", "│", "└", "─", "┘"),  # 单线框
        3: ("", "─", "", "", "", "", ""),  # 下划线
    }

    def __init__(self, width: int = 78):
        self.width = width

    def convert(self, markdown: str, verbose: bool = False) -> str:
        """
        将 Markdown 转换为终端友好格式

        Args:
            markdown: Markdown 文本
            verbose: 是否显示详细内容

        Returns:
            终端格式化文本
        """
        lines = markdown.split("\n")
        output_lines: List[str] = []
        in_code_block = False
        code_block_lines: List[str] = []
        skip_until_next_header = False

        for line in lines:
            # 跳过面包屑导航
            if line.startswith("**导航**"):
                continue

            # 处理代码块
            if line.startswith("```"):
                if in_code_block:
                    # 结束代码块
                    output_lines.append("─" * min(72, self.width))
                    output_lines.extend(code_block_lines)
                    output_lines.append("─" * min(72, self.width))
                    code_block_lines = []
                in_code_block = not in_code_block
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # 非详细模式下跳过某些内容
            if not verbose and skip_until_next_header:
                if line.startswith("#"):
                    skip_until_next_header = False
                else:
                    continue

            # 处理标题
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                level = len(header_match.group(1))
                title = self._clean_title(header_match.group(2))

                # 非详细模式下跳过深层标题内容
                if not verbose and level >= 4:
                    skip_until_next_header = True
                    continue

                output_lines.append("")
                output_lines.extend(self._format_header(title, level))
                continue

            # 处理列表项
            list_match = re.match(r"^(\s*)[-*]\s+(.+)$", line)
            if list_match:
                indent = len(list_match.group(1))
                content = self._process_inline(list_match.group(2))
                prefix = "  " * (indent // 2) + "• "
                output_lines.append(prefix + content)
                continue

            # 处理有序列表
            ordered_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
            if ordered_match:
                indent = len(ordered_match.group(1))
                num = ordered_match.group(2)
                content = self._process_inline(ordered_match.group(3))
                prefix = "  " * (indent // 2) + f"{num}. "
                output_lines.append(prefix + content)
                continue

            # 处理表格（简化处理）
            if line.startswith("|"):
                output_lines.append(self._process_table_row(line))
                continue

            # 处理分隔线
            if re.match(r"^---+$", line.strip()):
                output_lines.append("")
                continue

            # 处理普通段落
            processed = self._process_inline(line)
            output_lines.append(processed)

        return "\n".join(output_lines)

    def _clean_title(self, title: str) -> str:
        """清理标题中的 emoji 和链接"""
        # 移除链接语法但保留文本
        title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
        return title.strip()

    def _format_header(self, title: str, level: int) -> List[str]:
        """格式化标题"""
        if level == 1:
            # 一级标题：双线框
            width = min(self.width, max(len(title) + 4, 60))
            top = "╔" + "═" * (width - 2) + "╗"
            mid = "║ " + title.center(width - 4) + " ║"
            bot = "╚" + "═" * (width - 2) + "╝"
            return [top, mid, bot]
        elif level == 2:
            # 二级标题：单线框
            width = min(self.width, max(len(title) + 4, 50))
            top = "┌" + "─" * (width - 2) + "┐"
            mid = "│ " + title.ljust(width - 4) + " │"
            bot = "└" + "─" * (width - 2) + "┘"
            return [top, mid, bot]
        elif level == 3:
            # 三级标题：加粗 + 下划线
            return [title, "─" * len(title)]
        else:
            # 其他级别：缩进 + 符号
            prefix = "  " * (level - 3) + "► "
            return [prefix + title]

    def _process_inline(self, text: str) -> str:
        """处理行内格式"""
        # 移除链接但保留文本
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # 处理加粗
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        # 处理斜体
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        # 处理行内代码
        text = re.sub(r"`([^`]+)`", r"`\1`", text)
        return text

    def _process_table_row(self, line: str) -> str:
        """处理表格行"""
        # 简单处理：保留表格格式
        return line


@export
class DocReader:
    """文档读取器"""

    def __init__(self):
        self._docs_root: Optional[Path] = None
        self._converter = MarkdownToTerminal()
        self._cache: Dict[str, str] = {}

    @property
    def docs_root(self) -> Optional[Path]:
        """懒加载 docs 目录"""
        if self._docs_root is None:
            self._docs_root = find_docs_root()
        return self._docs_root

    def is_available(self) -> bool:
        """检查文档是否可用"""
        return self.docs_root is not None

    def read_topic(
        self, topic: str, verbose: bool = False, fallback: Optional[str] = None
    ) -> Tuple[str, bool]:
        """
        读取指定主题的文档

        Args:
            topic: 主题名称
            verbose: 是否显示详细内容
            fallback: 回退内容

        Returns:
            (内容, 是否来自文档) 元组
        """
        cache_key = f"{topic}:{verbose}"
        if cache_key in self._cache:
            return self._cache[cache_key], True

        if not self.is_available():
            return fallback or f"文档目录不可用，主题: {topic}", False

        doc_files = TOPIC_DOC_MAPPING.get(topic, [])
        if not doc_files:
            return fallback or f"未找到主题 '{topic}' 的文档映射", False

        # 读取并合并文档
        contents: List[str] = []
        docs_root = self.docs_root  # 类型收窄
        assert docs_root is not None  # is_available() 已检查
        for doc_file in doc_files:
            doc_path = docs_root / doc_file
            if doc_path.exists():
                try:
                    markdown = doc_path.read_text(encoding="utf-8")
                    converted = self._converter.convert(markdown, verbose)
                    contents.append(converted)
                except Exception as e:
                    contents.append(f"读取 {doc_file} 失败: {e}")

        if not contents:
            return fallback or f"未找到主题 '{topic}' 的文档文件", False

        result = "\n\n".join(contents)
        self._cache[cache_key] = result
        return result, True

    def read_file(self, relative_path: str, verbose: bool = False) -> Optional[str]:
        """
        读取指定文档文件

        Args:
            relative_path: 相对于 docs/ 的路径
            verbose: 是否显示详细内容

        Returns:
            转换后的内容，失败返回 None
        """
        if not self.is_available():
            return None

        docs_root = self.docs_root  # 类型收窄
        assert docs_root is not None  # is_available() 已检查
        doc_path = docs_root / relative_path
        if not doc_path.exists():
            return None

        try:
            markdown = doc_path.read_text(encoding="utf-8")
            return self._converter.convert(markdown, verbose)
        except Exception:
            return None

    def list_available_docs(self) -> Dict[str, List[str]]:
        """列出所有可用的文档映射"""
        result = {}
        for topic, files in TOPIC_DOC_MAPPING.items():
            available = []
            if self.docs_root:
                for f in files:
                    if (self.docs_root / f).exists():
                        available.append(f)
            result[topic] = available
        return result

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局实例
_doc_reader: Optional[DocReader] = None


@export
def get_doc_reader() -> DocReader:
    """获取全局文档读取器实例"""
    global _doc_reader
    if _doc_reader is None:
        _doc_reader = DocReader()
    return _doc_reader
