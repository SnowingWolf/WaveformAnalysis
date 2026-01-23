"""
元数据提取器 - 从代码中提取文档信息

从类、方法、插件等提取 docstrings、类型提示和元数据。
"""

import inspect
import re
from typing import Any, Dict, List, Type

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def format_docstring_to_markdown(docstring: str) -> str:
    """
    将 Google/NumPy 风格的 docstring 转换为 Markdown 格式

    识别并格式化 Args、Returns、Examples、Yields、Raises 等部分。

    Args:
        docstring: 原始 docstring 文本

    Returns:
        格式化后的 Markdown 文本
    """
    if not docstring:
        return ""

    lines = docstring.split('\n')
    result = []
    current_section = None
    section_content = []

    # 识别的章节标题（支持中英文）
    section_headers = {
        # 英文
        'Args:', 'Arguments:', 'Parameters:',
        'Returns:', 'Return:',
        'Yields:', 'Yield:',
        'Raises:', 'Raise:',
        'Examples:', 'Example:',
        'Note:', 'Notes:',
        'Warning:', 'Warnings:',
        'See Also:', 'References:',
        # 中文
        '参数:', '参数：',
        '返回:', '返回：',
        '抛出:', '抛出：', '异常:', '异常：',
        '示例:', '示例：',
        '注意:', '注意：',
        '警告:', '警告：',
    }

    def flush_section():
        """输出当前章节"""
        if current_section is None:
            # 普通文本
            result.extend(section_content)
        elif current_section in ['Examples:', 'Example:', '示例:', '示例：']:
            # 示例部分已经在模板中单独处理，这里跳过
            pass
        elif current_section in ['Args:', 'Arguments:', 'Parameters:', '参数:', '参数：']:
            # 参数列表格式化
            if section_content:
                result.append('\n**参数:**\n')
                result.extend(format_args_section(section_content))
        elif current_section in ['Returns:', 'Return:', '返回:', '返回：']:
            # 返回值格式化
            if section_content:
                result.append('\n**返回:**\n')
                result.extend(format_returns_section(section_content))
        elif current_section in ['Raises:', 'Raise:', '抛出:', '抛出：', '异常:', '异常：']:
            # 异常格式化
            if section_content:
                result.append('\n**异常:**\n')
                result.extend(format_raises_section(section_content))
        elif current_section in ['Note:', 'Notes:', '注意:', '注意：']:
            # 注释
            if section_content:
                result.append('\n**注意:**\n')
                result.extend(section_content)
        elif current_section in ['Warning:', 'Warnings:', '警告:', '警告：']:
            # 警告
            if section_content:
                result.append('\n**警告:**\n')
                result.extend(section_content)
        else:
            # 其他章节
            result.append(f'\n**{current_section.rstrip(":：")}:**\n')
            result.extend(section_content)

    def format_args_section(lines):
        """格式化参数章节"""
        formatted = []
        current_param = None
        param_desc = []

        for line in lines:
            # 检测参数行（格式：param_name: 描述）
            match = re.match(r'^(\s*)(\w+):\s*(.*)', line)
            if match:
                # 保存上一个参数
                if current_param:
                    formatted.append(f"- `{current_param}`: {' '.join(param_desc)}\n")

                # 开始新参数
                current_param = match.group(2)
                param_desc = [match.group(3)] if match.group(3) else []
            else:
                # 参数描述的续行
                stripped = line.strip()
                if stripped and current_param:
                    param_desc.append(stripped)

        # 保存最后一个参数
        if current_param:
            formatted.append(f"- `{current_param}`: {' '.join(param_desc)}\n")

        return formatted

    def format_returns_section(lines):
        """格式化返回值章节"""
        # 简单合并所有行
        text = ' '.join(line.strip() for line in lines if line.strip())
        return [f"\n{text}\n"]

    def format_raises_section(lines):
        """格式化异常章节"""
        formatted = []
        for line in lines:
            match = re.match(r'^(\s*)(\w+):\s*(.*)', line)
            if match:
                exc_type = match.group(2)
                desc = match.group(3)
                formatted.append(f"- `{exc_type}`: {desc}\n")
            else:
                stripped = line.strip()
                if stripped and formatted:
                    # 续行，添加到最后一项
                    formatted[-1] = formatted[-1].rstrip('\n') + ' ' + stripped + '\n'
        return formatted

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测章节标题
        if stripped in section_headers:
            # 输出之前的章节
            flush_section()

            # 开始新章节
            current_section = stripped
            section_content = []
        else:
            # 普通行，添加到当前章节
            section_content.append(line + '\n')

        i += 1

    # 输出最后一个章节
    flush_section()

    return ''.join(result).strip()


# 保留原有函数以便向后兼容
def format_docstring(docstring: str) -> str:
    """向后兼容的包装函数"""
    return format_docstring_to_markdown(docstring)


@export
class MetadataExtractor:
    """从代码中提取元数据"""

    def extract_class_api(self, cls: Type) -> Dict[str, Any]:
        """
        提取类的 API 信息

        Args:
            cls: 要提取的类

        Returns:
            包含类名、文档、方法列表的字典
        """
        methods = []

        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            # 跳过私有方法
            if name.startswith('_') and name != '__init__':
                continue

            # 提取方法签名
            try:
                sig = inspect.signature(method)
                signature = str(sig)
            except (ValueError, TypeError):
                signature = '(...)'

            # 提取文档字符串
            doc = inspect.getdoc(method) or ''

            # 提取示例代码
            examples = self.extract_examples_from_docstring(doc)

            # 格式化 docstring 为 Markdown
            formatted_doc = format_docstring_to_markdown(doc)

            methods.append({
                'name': name,
                'signature': signature,
                'doc': formatted_doc,  # 使用格式化后的文档
                'doc_raw': doc,         # 保留原始文档以供模板选择
                'examples': examples,
            })

        return {
            'name': cls.__name__,
            'doc': inspect.getdoc(cls) or '',
            'methods': sorted(methods, key=lambda m: m['name']),
        }

    def extract_plugin_metadata(self, plugin) -> Dict[str, Any]:
        """
        提取插件元数据

        Args:
            plugin: 插件实例

        Returns:
            包含插件信息的字典
        """
        metadata = {
            'class_name': plugin.__class__.__name__,
            'provides': plugin.provides,
            'depends_on': plugin.depends_on,
            'version': getattr(plugin, 'version', 'unknown'),
            'doc': inspect.getdoc(plugin.__class__) or '',
            'options': [],
        }

        # 提取配置选项
        if hasattr(plugin, 'options'):
            for opt_name, opt in plugin.options.items():
                opt_info = {
                    'name': opt_name,
                    'default': str(getattr(opt, 'default', 'N/A')),
                    'type': str(getattr(opt, 'type', 'Any')),
                    'help': getattr(opt, 'help', ''),
                }
                metadata['options'].append(opt_info)

        return metadata

    def extract_plugin_configs(self, ctx) -> Dict[str, Any]:
        """
        提取所有插件的配置信息

        Args:
            ctx: Context 实例

        Returns:
            配置信息字典
        """
        configs = {}

        if not hasattr(ctx, '_plugins'):
            return configs

        for plugin_name, plugin in ctx._plugins.items():
            metadata = self.extract_plugin_metadata(plugin)
            configs[plugin_name] = metadata

        return configs

    def extract_examples_from_docstring(self, docstring: str) -> List[str]:
        """
        从 docstring 中提取示例代码

        Args:
            docstring: 文档字符串

        Returns:
            示例代码列表
        """
        examples = []

        if not docstring:
            return examples

        lines = docstring.split('\n')
        in_example = False
        current_example = []

        for line in lines:
            # 检测示例块开始
            if 'Examples:' in line or 'Example:' in line:
                in_example = True
                continue

            # 检测示例块结束（空行后跟非缩进行）
            if in_example:
                if line.strip() == '':
                    if current_example:
                        examples.append('\n'.join(current_example))
                        current_example = []
                    in_example = False
                elif line.startswith('    ') or line.startswith('\t'):
                    # 去除缩进
                    current_example.append(line.strip())
                else:
                    # 非缩进行，示例结束
                    if current_example:
                        examples.append('\n'.join(current_example))
                        current_example = []
                    in_example = False

        # 添加最后一个示例
        if current_example:
            examples.append('\n'.join(current_example))

        return examples

    def extract_method_params(self, method) -> List[Dict[str, Any]]:
        """
        提取方法参数信息

        Args:
            method: 方法对象

        Returns:
            参数信息列表
        """
        params = []

        try:
            sig = inspect.signature(method)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                param_info = {
                    'name': param_name,
                    'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
                    'default': str(param.default) if param.default != inspect.Parameter.empty else None,
                }
                params.append(param_info)
        except (ValueError, TypeError):
            pass

        return params
