# -*- coding: utf-8 -*-
"""
波形预览模块 - 轻量级波形快速预览工具

本模块提供轻量级的波形预览功能，允许在完整数据处理前快速查看原始波形数据，
用于确定阈值、基线等参数。

主要特性:
- 无需完整处理流程
- 支持按事件范围或时间戳范围选择波形
- 提供叠加显示和分格显示两种可视化模式
- 自动标注基线、峰值、积分区域等关键特征

典型使用场景:
- 数据处理前快速查看原始波形
- 确定阈值、基线等处理参数
- 验证数据质量
- 选择感兴趣的事件进行详细分析
"""

import logging
from typing import Dict, List, Optional, Tuple

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.processing.loader import WaveformLoaderCSV
from waveform_analysis.core.processing.processor import DEFAULT_WAVE_LENGTH, RECORD_DTYPE
from waveform_analysis.utils.io import parse_files_generator

# 初始化 logger 和 exporter
logger = logging.getLogger(__name__)
export, __all__ = exporter()


@export
class WaveformPreviewer:
    """
    轻量级波形预览器，快速查看原始波形数据。

    该类提供快速加载和可视化原始波形数据的功能，无需运行完整的
    完整处理流程。适合在数据处理前快速查看数据质量
    和确定处理参数。

    参数:
        run_name: 运行名称，对应 DAQ 数据目录名
        data_root: DAQ 数据根目录，默认为 "DAQ"
        n_channels: 通道总数，默认为 6
        daq_adapter: DAQ 适配器名称（如 "vx2730"），用于处理不同格式

    示例:
        >>> previewer = WaveformPreviewer(
        ...     run_name="49V_OV_circulation_CH0_Coincidence_20dB",
        ...     n_channels=4
        ... )
        >>> waveforms = previewer.load_by_range(channel=0, start_event=0, end_event=10)
        >>> fig = previewer.plot_grid(waveforms, annotate=True)
    """

    def __init__(
        self,
        run_name: str,
        data_root: str = "DAQ",
        n_channels: int = 6,
        daq_adapter: Optional[str] = None,
    ):
        """
        初始化波形预览器。

        参数:
            run_name: 运行名称
            data_root: 数据根目录
            n_channels: 通道总数
            daq_adapter: DAQ 适配器名称（如 "vx2730"）
        """
        self.run_name = run_name
        self.data_root = data_root
        self.n_channels = n_channels
        self.daq_adapter = daq_adapter

        # 初始化加载器
        self._loader = WaveformLoaderCSV(
            n_channels=n_channels,
            run_name=run_name,
            data_root=data_root,
            daq_adapter=daq_adapter,
        )

        # 缓存文件列表
        self._raw_files = None

        logger.debug(
            f"WaveformPreviewer initialized: run_name={run_name}, "
            f"n_channels={n_channels}, data_root={data_root}, daq_adapter={daq_adapter}"
        )

    def _get_raw_files(self) -> List[List[str]]:
        """
        获取原始文件列表（带缓存）。

        返回:
            每个通道的文件列表
        """
        if self._raw_files is None:
            self._raw_files = self._loader.get_raw_files()
            logger.debug(f"Loaded file lists for {len(self._raw_files)} channels")
        return self._raw_files

    def load_by_range(self, channel: int, start_event: int, end_event: int) -> np.ndarray:
        """
        按事件范围加载波形数据。

        使用流式读取策略，仅加载指定范围的事件，避免加载所有数据。

        参数:
            channel: 通道号（0-based）
            start_event: 起始事件索引（包含）
            end_event: 结束事件索引（不包含）

        返回:
            结构化数组（RECORD_DTYPE），包含 baseline, timestamp, channel, wave 等字段

        示例:
            >>> waveforms = previewer.load_by_range(channel=0, start_event=10, end_event=20)
            >>> print(f"Loaded {len(waveforms)} events")
        """
        # 1. 获取通道文件列表
        raw_files = self._get_raw_files()

        if channel >= len(raw_files):
            logger.warning(f"Channel {channel} does not exist (n_channels={self.n_channels})")
            return np.zeros(0, dtype=RECORD_DTYPE)

        channel_files = raw_files[channel]

        if not channel_files:
            logger.warning(f"No files found for channel {channel}")
            return np.zeros(0, dtype=RECORD_DTYPE)

        # 2. 流式读取并累计事件计数
        collected = []
        event_counter = 0

        logger.debug(f"Loading events {start_event} to {end_event} from channel {channel}")

        for chunk in parse_files_generator(channel_files, chunksize=1000):
            chunk_size = len(chunk)
            chunk_end = event_counter + chunk_size

            # 判断是否包含目标范围
            if chunk_end <= start_event:
                # 当前 chunk 在目标范围之前，跳过
                event_counter = chunk_end
                continue

            if event_counter >= end_event:
                # 已超出目标范围，停止读取
                break

            # 计算在当前 chunk 中需要提取的片段
            local_start = max(0, start_event - event_counter)
            local_end = min(chunk_size, end_event - event_counter)

            collected.append(chunk[local_start:local_end])
            event_counter = chunk_end

            if event_counter >= end_event:
                break

        # 3. 合并并结构化
        if not collected:
            logger.warning(f"No events found in range [{start_event}, {end_event}) for channel {channel}")
            return np.zeros(0, dtype=RECORD_DTYPE)

        raw_data = np.vstack(collected)
        logger.debug(f"Loaded {len(raw_data)} events, structuring...")

        return self._structure_minimal(raw_data, channel)

    def load_by_timestamp(self, channel: int, start_ts: int, end_ts: int) -> np.ndarray:
        """
        按时间戳范围加载波形数据。

        流式扫描文件，筛选时间戳在指定范围内的事件。

        参数:
            channel: 通道号（0-based）
            start_ts: 起始时间戳（ps，包含）
            end_ts: 结束时间戳（ps，不包含）

        返回:
            结构化数组（RECORD_DTYPE）

        示例:
            >>> waveforms = previewer.load_by_timestamp(
            ...     channel=0,
            ...     start_ts=1000000000000,  # 1e12 ps = 1 秒
            ...     end_ts=1002000000000     # 1.002 秒
            ... )
        """
        # 1. 获取通道文件列表
        raw_files = self._get_raw_files()

        if channel >= len(raw_files):
            logger.warning(f"Channel {channel} does not exist (n_channels={self.n_channels})")
            return np.zeros(0, dtype=RECORD_DTYPE)

        channel_files = raw_files[channel]

        if not channel_files:
            logger.warning(f"No files found for channel {channel}")
            return np.zeros(0, dtype=RECORD_DTYPE)

        # 2. 流式扫描，筛选时间戳范围
        collected = []

        logger.debug(f"Loading events with timestamp in [{start_ts}, {end_ts}) from channel {channel}")

        for chunk in parse_files_generator(channel_files, chunksize=1000):
            # 提取时间戳列（CSV 第3列，索引为2）
            try:
                timestamps = chunk[:, 2].astype(np.int64)
            except (IndexError, ValueError) as e:
                logger.debug(f"Failed to extract timestamps from chunk: {e}")
                continue

            # 筛选在目标范围内的事件
            mask = (timestamps >= start_ts) & (timestamps < end_ts)

            if np.any(mask):
                collected.append(chunk[mask])

            # 提前停止优化：如果当前 chunk 的最小时间戳已超过 end_ts
            if len(timestamps) > 0 and np.min(timestamps) >= end_ts:
                logger.debug(f"Stopping early: min_ts={np.min(timestamps)} >= end_ts={end_ts}")
                break

        # 3. 合并并结构化
        if not collected:
            logger.warning(f"No events found in timestamp range [{start_ts}, {end_ts}) for channel {channel}")
            return np.zeros(0, dtype=RECORD_DTYPE)

        raw_data = np.vstack(collected)
        logger.debug(f"Loaded {len(raw_data)} events, structuring...")

        return self._structure_minimal(raw_data, channel)

    def _structure_minimal(self, raw_data: np.ndarray, channel: int) -> np.ndarray:
        """
        轻量级结构化：仅提取预览所需字段。

        与 WaveformStruct._structure_waveform 的区别：
        - 不处理 BOARD/CHANNEL 映射（已知单通道）
        - 不填充完整 RECORD_DTYPE（仅需 baseline, timestamp, wave）
        - 更快速、更轻量

        参数:
            raw_data: 原始 CSV 数据（NumPy 数组）
            channel: 通道号

        返回:
            结构化数组（RECORD_DTYPE）
        """
        n_events = len(raw_data)
        result = np.zeros(n_events, dtype=RECORD_DTYPE)

        # 提取基线（前40个采样点均值，对应CSV第7-46列）
        try:
            baseline_vals = np.mean(raw_data[:, 7:47].astype(float), axis=1)
        except (IndexError, ValueError) as e:
            logger.debug(f"Failed to compute baseline: {e}, using zeros")
            baseline_vals = np.zeros(n_events)

        # 提取时间戳（CSV第3列，索引为2）
        try:
            timestamps = raw_data[:, 2].astype(np.int64)
        except (IndexError, ValueError) as e:
            logger.debug(f"Failed to extract timestamps: {e}, using zeros")
            timestamps = np.zeros(n_events, dtype=np.int64)

        # 提取波形（CSV第7列开始，最多800个采样点）
        try:
            wave_data = raw_data[:, 7:]
            n_samples = min(wave_data.shape[1], DEFAULT_WAVE_LENGTH)
            result["wave"][:, :n_samples] = wave_data[:, :n_samples].astype(np.float32)
        except (IndexError, ValueError) as e:
            logger.debug(f"Failed to extract waveforms: {e}")

        result["baseline"] = baseline_vals
        result["timestamp"] = timestamps
        result["channel"] = channel
        result["event_length"] = 0  # 不计算，保持为0

        logger.debug(f"Structured {n_events} events for channel {channel}")

        return result

    def compute_features(
        self,
        waveforms: np.ndarray,
        peaks_range: Tuple[int, int] = FeatureDefaults.PEAK_RANGE,
        charge_range: Tuple[int, int] = FeatureDefaults.CHARGE_RANGE,
    ) -> Dict[str, np.ndarray]:
        """
        计算波形特征。

        参数:
            waveforms: 结构化数组（RECORD_DTYPE）
            peaks_range: 峰值检测区间（采样点索引），默认 (40, 90)
            charge_range: 电荷积分区间（采样点索引），默认 (60, 400)

        返回:
            包含以下键的字典:
            - 'peaks': 峰值数组（ADC counts）
            - 'charges': 电荷数组（ADC counts）
            - 'peak_positions': 峰值位置数组（采样点索引）
            - 'baselines': 基线数组（ADC counts）

        示例:
            >>> features = previewer.compute_features(waveforms)
            >>> print(f"Mean peak: {features['peaks'].mean():.2f}")
        """
        if len(waveforms) == 0:
            return {
                "peaks": np.array([]),
                "charges": np.array([]),
                "peak_positions": np.array([]),
                "baselines": np.array([]),
            }

        baselines = waveforms["baseline"]
        waves = waveforms["wave"]

        # 峰值和峰值位置
        wave_seg_p = waves[:, peaks_range[0] : peaks_range[1]]
        # 峰值 = baseline - wave 的最大值（假设负脉冲）
        peaks = np.max(baselines[:, None] - wave_seg_p, axis=1)
        peak_positions = peaks_range[0] + np.argmax(baselines[:, None] - wave_seg_p, axis=1)

        # 电荷积分
        wave_seg_c = waves[:, charge_range[0] : charge_range[1]]
        charges = np.sum(baselines[:, None] - wave_seg_c, axis=1)

        return {
            "peaks": peaks,
            "charges": charges,
            "peak_positions": peak_positions,
            "baselines": baselines,
        }

    def plot_overlay(
        self,
        waveforms: np.ndarray,
        annotate: bool = True,
        peaks_range: Tuple[int, int] = FeatureDefaults.PEAK_RANGE,
        charge_range: Tuple[int, int] = FeatureDefaults.CHARGE_RANGE,
        figsize: Tuple[int, int] = (12, 6),
        sampling_interval_ns: float = 2.0,
        **kwargs,
    ) -> Figure:
        """
        叠加显示多个波形。

        在同一图上叠加显示多个波形，可选地标注关键特征（基线、峰值、积分区域）。

        参数:
            waveforms: 结构化数组（RECORD_DTYPE）
            annotate: 是否标注特征（基线、峰值、积分区域），默认 True
            peaks_range: 峰值检测区间，默认 (40, 90)
            charge_range: 电荷积分区间，默认 (60, 400)
            figsize: 图像大小，默认 (12, 6)
            sampling_interval_ns: 采样间隔（ns），默认 2.0
            **kwargs: 额外参数
                - baseline_color: 基线颜色，默认 'gray'
                - peak_marker: 峰值标记，默认 'r*'
                - integration_color: 积分区域颜色，默认 'yellow'
                - integration_alpha: 积分区域透明度，默认 0.15
                - show_legend: 是否显示图例，默认 True
                - title: 自定义标题

        返回:
            Matplotlib Figure 对象

        示例:
            >>> fig = previewer.plot_overlay(waveforms[:10], annotate=True)
            >>> plt.show()
        """
        if len(waveforms) == 0:
            logger.warning("No waveforms to plot")
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(
                0.5,
                0.5,
                "No waveforms to display",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            return fig

        fig, ax = plt.subplots(figsize=figsize)

        # 计算特征（用于标注）
        if annotate:
            features = self.compute_features(waveforms, peaks_range, charge_range)

        # 标注积分区域（在所有波形之前绘制，避免遮挡）
        if annotate:
            ax.axvspan(
                charge_range[0] * sampling_interval_ns,
                charge_range[1] * sampling_interval_ns,
                alpha=kwargs.get("integration_alpha", 0.15),
                color=kwargs.get("integration_color", "yellow"),
                label="Integration Window",
                zorder=0,
            )

        # 绘制每个波形
        for i, record in enumerate(waveforms):
            wave = record["wave"]
            baseline = record["baseline"]
            timestamp = record["timestamp"]

            # 时间轴（ns）
            x = np.arange(len(wave)) * sampling_interval_ns

            # 绘制波形
            ax.plot(x, wave, alpha=0.6, linewidth=1.5, label=f"Event {i}", zorder=2)

            # 标注基线（只标注第一个波形的基线，避免重复）
            if annotate and i == 0:
                ax.axhline(
                    baseline,
                    color=kwargs.get("baseline_color", "gray"),
                    linestyle="--",
                    alpha=0.5,
                    label="Baseline (Event 0)",
                    zorder=1,
                )

            # 标注峰值位置（只标注前几个波形，避免过于拥挤）
            if annotate and i < min(5, len(waveforms)):
                peak_pos = features["peak_positions"][i]
                peak_val = wave[peak_pos]
                ax.plot(
                    peak_pos * sampling_interval_ns,
                    peak_val,
                    kwargs.get("peak_marker", "r*"),
                    markersize=12,
                    zorder=3,
                )

        ax.set_xlabel("Time [ns]", fontsize=12)
        ax.set_ylabel("ADC Value", fontsize=12)

        title = kwargs.get(
            "title",
            f"Waveform Overlay - Channel {waveforms[0]['channel']} ({len(waveforms)} events)",
        )
        ax.set_title(title, fontsize=14)

        if kwargs.get("show_legend", True):
            ax.legend(fontsize=8, loc="best")

        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        return fig

    def plot_grid(
        self,
        waveforms: np.ndarray,
        annotate: bool = True,
        peaks_range: Tuple[int, int] = FeatureDefaults.PEAK_RANGE,
        charge_range: Tuple[int, int] = FeatureDefaults.CHARGE_RANGE,
        ncols: int = 2,
        figsize_per_plot: Tuple[int, int] = (6, 4),
        sampling_interval_ns: float = 2.0,
        **kwargs,
    ) -> Figure:
        """
        分格显示每个波形（每个波形一个子图）。

        参数:
            waveforms: 结构化数组（RECORD_DTYPE）
            annotate: 是否标注特征，默认 True
            peaks_range: 峰值检测区间，默认 (40, 90)
            charge_range: 电荷积分区间，默认 (60, 400)
            ncols: 列数，默认 2
            figsize_per_plot: 每个子图大小，默认 (6, 4)
            sampling_interval_ns: 采样间隔（ns），默认 2.0
            **kwargs: 额外参数
                - share_y: 共享 Y 轴，默认 False
                - show_title: 是否显示子图标题，默认 True
                - title_fontsize: 子图标题字号，默认 10

        返回:
            Matplotlib Figure 对象

        示例:
            >>> fig = previewer.plot_grid(waveforms[:6], annotate=True, ncols=3)
            >>> plt.savefig('waveform_grid.png')
        """
        if len(waveforms) == 0:
            logger.warning("No waveforms to plot")
            fig, ax = plt.subplots(figsize=figsize_per_plot)
            ax.text(
                0.5,
                0.5,
                "No waveforms to display",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            return fig

        n_events = len(waveforms)
        nrows = (n_events + ncols - 1) // ncols
        figsize = (figsize_per_plot[0] * ncols, figsize_per_plot[1] * nrows)

        fig, axes = plt.subplots(
            nrows,
            ncols,
            figsize=figsize,
            sharex=True,
            sharey=kwargs.get("share_y", False),
        )
        axes = np.atleast_2d(axes).flatten()

        # 计算特征（用于标注）
        if annotate:
            features = self.compute_features(waveforms, peaks_range, charge_range)

        for i, (record, ax) in enumerate(zip(waveforms, axes)):
            wave = record["wave"]
            baseline = record["baseline"]
            timestamp = record["timestamp"]

            # 时间轴（ns）
            x = np.arange(len(wave)) * sampling_interval_ns

            # 绘制波形
            ax.plot(x, wave, linewidth=1.5, color="blue")

            if annotate:
                # 基线
                ax.axhline(baseline, color="gray", linestyle="--", alpha=0.7)

                # 峰值
                peak_pos = features["peak_positions"][i]
                peak_val = wave[peak_pos]
                ax.plot(
                    peak_pos * sampling_interval_ns,
                    peak_val,
                    "r*",
                    markersize=10,
                )

                # 积分区域
                ax.axvspan(
                    charge_range[0] * sampling_interval_ns,
                    charge_range[1] * sampling_interval_ns,
                    alpha=0.15,
                    color="yellow",
                )

                # 标注数值
                charge = features["charges"][i]
                peak = features["peaks"][i]
                ax.text(
                    0.02,
                    0.98,
                    f"Peak: {peak:.1f}\nCharge: {charge:.1f}\nBaseline: {baseline:.2f}",
                    transform=ax.transAxes,
                    verticalalignment="top",
                    fontsize=8,
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
                )

            if kwargs.get("show_title", True):
                ax.set_title(
                    f"Event {i} (ts={timestamp})",
                    fontsize=kwargs.get("title_fontsize", 10),
                )
            ax.grid(True, alpha=0.3)

        # 隐藏多余的子图
        for j in range(i + 1, len(axes)):
            axes[j].axis("off")

        # 添加全局轴标签
        fig.text(0.5, 0.04, "Time [ns]", ha="center", fontsize=12)
        fig.text(0.04, 0.5, "ADC Value", va="center", rotation="vertical", fontsize=12)
        plt.tight_layout(rect=[0.05, 0.05, 1, 1])

        return fig


@export
def preview_waveforms(
    run_name: str,
    channel: int,
    event_range: Optional[Tuple[int, int]] = None,
    timestamp_range: Optional[Tuple[int, int]] = None,
    plot_mode: str = "overlay",
    annotate: bool = True,
    save_path: Optional[str] = None,
    data_root: str = "DAQ",
    n_channels: int = 6,
    **kwargs,
) -> Figure:
    """
    便捷函数：一站式波形预览。

    参数:
        run_name: 运行名称
        channel: 通道号
        event_range: 事件范围 (start, end)，与 timestamp_range 二选一
        timestamp_range: 时间戳范围 (start_ts, end_ts)，与 event_range 二选一
        plot_mode: 绘图模式，'overlay' 或 'grid'，默认 'overlay'
        annotate: 是否标注特征，默认 True
        save_path: 保存路径，默认 None（不保存）
        data_root: 数据根目录，默认 "DAQ"
        n_channels: 通道总数，默认 6
        **kwargs: 传递给 plot_overlay 或 plot_grid 的额外参数

    返回:
        Matplotlib Figure 对象

    示例:
        >>> fig = preview_waveforms(
        ...     run_name="49V_OV_circulation_CH0_Coincidence_20dB",
        ...     channel=0,
        ...     event_range=(10, 20),
        ...     plot_mode='grid',
        ...     annotate=True,
        ...     save_path='preview.png'
        ... )
    """
    # 检查参数
    if event_range is None and timestamp_range is None:
        raise ValueError("Must specify either event_range or timestamp_range")

    if event_range is not None and timestamp_range is not None:
        raise ValueError("Cannot specify both event_range and timestamp_range")

    # 初始化预览器
    previewer = WaveformPreviewer(run_name=run_name, data_root=data_root, n_channels=n_channels)

    # 加载波形
    if event_range is not None:
        start, end = event_range
        waveforms = previewer.load_by_range(channel, start, end)
    else:
        start_ts, end_ts = timestamp_range
        waveforms = previewer.load_by_timestamp(channel, start_ts, end_ts)

    # 绘图
    if plot_mode == "overlay":
        fig = previewer.plot_overlay(waveforms, annotate=annotate, **kwargs)
    elif plot_mode == "grid":
        fig = previewer.plot_grid(waveforms, annotate=annotate, **kwargs)
    else:
        raise ValueError(f"Invalid plot_mode: {plot_mode}. Must be 'overlay' or 'grid'")

    # 保存
    if save_path is not None:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Figure saved to {save_path}")

    return fig
