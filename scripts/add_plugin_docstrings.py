#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动为 standard.py 的所有插件 compute 方法添加 docstring

这个脚本会安全地为所有12个标准插件的 compute() 方法添加完整的 Google 风格 docstring。
"""

import re
from pathlib import Path

# 定义所有插件的 docstring
DOCSTRINGS = {
    'RawFilesPlugin': '''        """
        扫描数据目录并按通道分组原始 CSV 文件

        从配置的数据目录中查找指定运行的所有原始波形文件，并按通道号分组。
        支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。

        Args:
            context: Context 实例，用于访问配置和缓存
            run_id: 运行标识符（运行名称）
            **kwargs: 依赖数据（此插件无依赖）

        Returns:
            List[List[str]]: 按通道分组的文件路径列表

        Examples:
            >>> raw_files = ctx.get_data('run_001', 'raw_files')
            >>> print(f"通道数: {len(raw_files)}")
        """
''',
    'WaveformsPlugin': '''        """
        从原始 CSV 文件中提取波形数据

        读取并解析原始 CSV 文件，提取每个通道的波形数据。
        支持并行处理加速，可配置使用线程池或进程池进行通道级并行。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 raw_files（由 RawFilesPlugin 提供）

        Returns:
            List[np.ndarray]: 每个通道的波形数据列表

        Examples:
            >>> waveforms = ctx.get_data('run_001', 'waveforms')
            >>> print(f"通道0波形形状: {waveforms[0].shape}")
        """
''',
    'StWaveformsPlugin': '''        """
        将波形数据结构化为 NumPy 结构化数组

        将原始波形列表转换为包含时间戳、基线、通道号和波形数据的结构化数组。
        这是数据流中的关键步骤，为后续特征提取提供统一的数据格式。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 waveforms（由 WaveformsPlugin 提供）

        Returns:
            List[np.ndarray]: 每个通道的结构化数组，dtype 为 RECORD_DTYPE

        Examples:
            >>> st_waveforms = ctx.get_data('run_001', 'st_waveforms')
            >>> print(st_waveforms[0].dtype.names)
        """
''',
    'HitFinderPlugin': '''        """
        从结构化波形中检测 Hit 事件

        使用阈值法从波形中识别和定位 Hit（超过阈值的信号峰值）。
        返回每个 Hit 的时间、面积、高度和宽度等特征。

        Args:
            context: Context 实例
            run_id: 运行标识符
            threshold: Hit 检测阈值（默认10.0）
            **kwargs: 依赖数据，包含 st_waveforms

        Returns:
            List[np.ndarray]: 每个通道的 Hit 列表，dtype 为 PEAK_DTYPE

        Examples:
            >>> hits = ctx.get_data('run_001', 'hits')
            >>> print(f"通道0的Hit数: {len(hits[0])}")
        """
''',
    'BasicFeaturesPlugin': '''        """
        计算基础波形特征（峰值和电荷）

        .. deprecated::
            建议使用 PeaksPlugin 和 ChargesPlugin 替代

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms

        Returns:
            Dict[str, List[np.ndarray]]: 包含 'peaks' 和 'charges' 的字典
        """
''',
    'PeaksPlugin': '''        """
        从结构化波形中计算峰值特征

        在配置的时间窗口内查找波形的最大峰值（最大值 - 最小值）。
        使用向量化计算，高效处理大量波形数据。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms

        Returns:
            List[np.ndarray]: 每个通道的峰值数组

        Examples:
            >>> peaks = ctx.get_data('run_001', 'peaks')
            >>> print(f"峰值范围: {peaks[0].min():.2f} - {peaks[0].max():.2f}")
        """
''',
    'ChargesPlugin': '''        """
        从结构化波形中计算电荷积分

        在配置的时间窗口内对波形进行积分（baseline - wave），计算总电荷。
        使用向量化计算提高效率。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms

        Returns:
            List[np.ndarray]: 每个通道的电荷数组

        Examples:
            >>> charges = ctx.get_data('run_001', 'charges')
            >>> print(f"电荷范围: {charges[0].min():.2f} - {charges[0].max():.2f}")
        """
''',
    'DataFramePlugin': '''        """
        构建单通道事件的 DataFrame

        整合结构化波形、峰值和电荷特征，构建包含所有事件信息的 pandas DataFrame。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms, peaks, charges

        Returns:
            pd.DataFrame: 包含所有通道事件的 DataFrame

        Examples:
            >>> df = ctx.get_data('run_001', 'df')
            >>> print(f"总事件数: {len(df)}")
        """
''',
    'GroupedEventsPlugin': '''        """
        按时间窗口分组多通道事件

        在指定的时间窗口内识别多通道同时触发的事件，并将它们分组。
        支持 Numba 加速和多进程并行处理。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 df

        Returns:
            pd.DataFrame: 分组后的事件

        Examples:
            >>> df_events = ctx.get_data('run_001', 'df_events')
            >>> print(f"事件组数: {df_events['event_id'].nunique()}")
        """
''',
    'PairedEventsPlugin': '''        """
        配对跨通道的符合事件

        识别满足时间符合条件的多通道事件对，用于符合测量分析。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 df_events

        Returns:
            pd.DataFrame: 配对事件

        Examples:
            >>> df_paired = ctx.get_data('run_001', 'df_paired')
            >>> print(f"配对数: {len(df_paired)}")
        """
''',
    'FilterPlugin': '''        """
        对波形数据应用数字滤波

        支持多种滤波器类型（Butterworth、Gaussian、移动平均等）。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms

        Returns:
            List[np.ndarray]: 滤波后的结构化数组
        """
''',
    'WaveformRecognitionPlugin': '''        """
        高级波形识别和特征提取

        使用多种识别算法从波形中提取事件。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms 和可选的 filtered_waveforms

        Returns:
            List[np.ndarray]: 识别出的事件列表
        """
''',
}

def add_docstrings(filepath='waveform_analysis/core/plugins/builtin/standard.py'):
    """为 compute 方法添加 docstring"""

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 为每个插件添加 docstring
    for plugin_name, docstring in DOCSTRINGS.items():
        # 查找 compute 方法定义的正则表达式
        # 匹配：def compute(self, context: Any, run_id: str, ...) -> ...:
        pattern = rf'(class {plugin_name}\(Plugin\):.*?)(def compute\(self,.*?\):)\s*\n(\s+)(\S)'

        def replacer(match):
            before_class = match.group(1)
            method_def = match.group(2)
            indent = match.group(3)
            first_code_char = match.group(4)

            # 检查是否已有 docstring
            if first_code_char in ('"', "'"):
                return match.group(0)  # 已有 docstring，跳过

            # 添加 docstring
            return f'{before_class}{method_def}\n{docstring}{indent}{first_code_char}'

        content = re.sub(pattern, replacer, content, flags=re.DOTALL)

    # 写回文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ 已为 {len(DOCSTRINGS)} 个插件添加 docstring")
    print(f"📄 文件: {filepath}")

if __name__ == '__main__':
    print("=" * 80)
    print("开始为标准插件添加 docstring...")
    print("=" * 80)
    print()

    add_docstrings()

    print()
    print("=" * 80)
    print("完成！请运行以下命令验证：")
    print("  python /tmp/analyze_docstrings.py")
    print("=" * 80)
