"""
Peak Channel 数据访问器

职责：
- 从 peak_id 获取 per-channel 数据（特征 + 波形）
- 分层加载：默认只加载特征层，按需加载波形层
- 索引优化：避免高频布尔筛选
- 集成可视化：提供绘图功能

使用示例：
    >>> accessor = PeakChannelAccessor(context, run_id)
    >>>
    >>> # 只获取特征（快速）
    >>> channels = accessor.get_peak_channels(peak_id=42)
    >>>
    >>> # 获取特征 + 波形
    >>> channels = accessor.get_peak_channel_data(peak_id=42, include_waveform=True)
    >>>
    >>> # 单独获取某个通道的波形
    >>> wf = accessor.get_channel_waveform(merged_index=10)
    >>>
    >>> # 绘制波形
    >>> fig, axes = accessor.plot(peak_id=42)
"""

from typing import Any, Optional

import numpy as np


class PeakChannelAccessor:
    """Peak 通道级数据访问器（特征 + 波形，分层加载）"""

    def __init__(self, context: Any, run_id: str, lazy_load: bool = False):
        """
        初始化数据访问器

        参数
        ----
        context : Context
            DAQAnalyzer 的 context 对象
        run_id : str
            Run ID
        lazy_load : bool, default=False
            如果为 True，延迟到首次访问时才加载特征层
        """
        self.context = context
        self.run_id = run_id

        # 特征层数据
        self._peaklet_components = None
        self._hit_merged = None
        self._hit_merged_features = None
        self._peaks = None

        # 波形层数据（延迟加载）
        self._records = None
        self._hit_threshold = None
        self._hit_merged_components = None
        self._wave_pool = None

        # 索引（延迟构建）
        self._peak_to_merged_idx = None  # {peak_id: [merged_index, ...]}
        self._record_id_to_idx = None  # {record_id: row_index}
        self._merged_to_hit_idx = None  # {merged_index: [hit_index, ...]}

        # 波形缓存
        self._waveform_cache = {}  # {merged_index: waveform_data}

        # 标志
        self._feature_layer_loaded = False
        self._waveform_layer_loaded = False

        if not lazy_load:
            self._load_feature_layer()

    def _load_feature_layer(self):
        """加载特征层数据"""
        if self._feature_layer_loaded:
            return

        self._peaklet_components = self.context.get_data(self.run_id, "peaklet_components")
        self._hit_merged = self.context.get_data(self.run_id, "hit_merged")
        self._hit_merged_features = self.context.get_data(self.run_id, "hit_merged_features")

        # peaks 是可选的
        try:
            self._peaks = self.context.get_data(self.run_id, "peaks")
        except Exception:
            self._peaks = None

        # 构建特征层索引
        self._build_feature_indices()

        self._feature_layer_loaded = True

    def _build_feature_indices(self):
        """构建特征层索引"""
        # peak_id -> merged_indices
        self._peak_to_merged_idx = {}
        for row in self._peaklet_components:
            peak_id = int(row["peak_id"])
            merged_idx = int(row["merged_index"])
            if peak_id not in self._peak_to_merged_idx:
                self._peak_to_merged_idx[peak_id] = []
            self._peak_to_merged_idx[peak_id].append(merged_idx)

    def _load_waveform_layer(self):
        """延迟加载波形层数据"""
        if self._waveform_layer_loaded:
            return

        self._records = self.context.get_data(self.run_id, "records")
        self._hit_threshold = self.context.get_data(self.run_id, "hit_threshold")
        self._hit_merged_components = self.context.get_data(self.run_id, "hit_merged_components")
        self._wave_pool = self.context.get_data(self.run_id, "wave_pool")

        # 构建波形层索引
        self._build_waveform_indices()

        self._waveform_layer_loaded = True

    def _build_waveform_indices(self):
        """构建波形层索引"""
        # record_id -> row index
        self._record_id_to_idx = {int(rec["record_id"]): i for i, rec in enumerate(self._records)}

        # merged_index -> hit_indices
        self._merged_to_hit_idx = {}
        for row in self._hit_merged_components:
            merged_idx = int(row["merged_index"])
            hit_idx = int(row["hit_index"])
            if merged_idx not in self._merged_to_hit_idx:
                self._merged_to_hit_idx[merged_idx] = []
            self._merged_to_hit_idx[merged_idx].append(hit_idx)

    def get_peak_channels(self, peak_id: int) -> list[dict]:
        """
        获取 peak 的所有通道特征（不加载波形）

        参数
        ----
        peak_id : int
            Peak ID

        返回
        ----
        list[dict]
            通道特征列表，每个 dict 包含：
            - peak_id: int
            - merged_index: int
            - board: int
            - channel: int
            - area: float
            - height: float
            - width: float
            - rise_time: float
            - fall_time: float
            - center_time: int
            - sample_start: int
            - sample_end: int
            - record_id: int
            - is_single_record: bool
        """
        self._load_feature_layer()

        # 通过索引获取 merged_indices（避免布尔筛选）
        merged_indices = self._peak_to_merged_idx.get(peak_id, [])

        channels = []
        for merged_idx in merged_indices:
            hm = self._hit_merged[merged_idx]
            feat = self._hit_merged_features[merged_idx]

            # 检查是否为单 record hit
            is_single_record = (
                bool(hm["is_single_record"])
                if "is_single_record" in self._hit_merged.dtype.names
                else int(hm["sample_start"]) >= 0 and int(hm["sample_end"]) >= 0
            )

            channels.append(
                {
                    "peak_id": peak_id,
                    "merged_index": int(merged_idx),
                    "board": int(hm["board"]),
                    "channel": int(hm["channel"]),
                    "area": float(feat["area"]),
                    "height": float(feat["height"]),
                    "width": float(feat["width"]),
                    "rise_time": float(feat["rise_time"]),
                    "fall_time": float(feat["fall_time"]),
                    "center_time": int(feat["center_time"]),
                    "sample_start": int(hm["sample_start"]),
                    "sample_end": int(hm["sample_end"]),
                    "record_id": int(hm["record_id"]),
                    "is_single_record": is_single_record,
                }
            )

        return channels

    def get_channel_waveform(self, merged_index: int, pad: int = 30) -> dict:
        """
        获取单个通道的波形

        参数
        ----
        merged_index : int
            Merged index (hit_merged 的行索引)
        pad : int, default=30
            在 hit 边界外扩展的采样点数

        返回
        ----
        dict
            波形数据，包含：
            - merged_index: int
            - board: int
            - channel: int
            - waveform: np.ndarray (拼接后的完整波形)
            - time_ns: np.ndarray (相对时间)
            - abs_time_ps: np.ndarray (绝对时间)
            - dt: int (采样间隔 ns)
            - is_single_record: bool
            - segments: list[dict] (原始片段信息，保留用于调试)
                每个 segment 包含：
                - waveform: np.ndarray
                - abs_time_ps: np.ndarray
                - dt: int
                - record_id: int
        """
        # 延迟加载波形层
        self._load_feature_layer()
        self._load_waveform_layer()

        # 检查缓存
        cache_key = (merged_index, pad)
        if cache_key in self._waveform_cache:
            return self._waveform_cache[cache_key]

        hm = self._hit_merged[merged_index]
        sample_start = int(hm["sample_start"])
        sample_end = int(hm["sample_end"])

        # 检查是否为单 record hit
        is_single_record = (
            bool(hm["is_single_record"])
            if "is_single_record" in self._hit_merged.dtype.names
            else sample_start >= 0 and sample_end >= 0
        )

        if is_single_record and sample_start >= 0 and sample_end >= 0:
            # 单 record hit
            result = self._extract_single_record_waveform(
                merged_index, sample_start, sample_end, pad
            )
        else:
            # 跨 record hit
            result = self._extract_multi_record_waveform(merged_index, pad)

        # 缓存结果
        self._waveform_cache[cache_key] = result

        return result

    def _extract_single_record_waveform(
        self, merged_index: int, sample_start: int, sample_end: int, pad: int
    ) -> dict:
        """从单个 record 提取波形"""
        hm = self._hit_merged[merged_index]
        record_id = int(hm["record_id"])

        # 通过索引获取 record（避免布尔筛选）
        rec_idx = self._record_id_to_idx[record_id]
        rec = self._records[rec_idx]

        dt_ns = int(rec["dt"])
        event_length = int(rec["event_length"])
        wave_offset = int(rec["wave_offset"])
        baseline = float(rec["baseline"])
        timestamp = int(rec["timestamp"])

        # 计算窗口范围（带 padding）
        s0 = max(0, sample_start - pad)
        s1 = min(event_length, sample_end + pad)

        # 提取原始波形
        raw = self._wave_pool[wave_offset + s0 : wave_offset + s1].astype(np.float32)

        # 根据极性计算信号
        polarity = str(rec["polarity"]) if "polarity" in rec.dtype.names else "negative"
        signal = raw - baseline if polarity == "positive" else baseline - raw

        # 计算时间轴
        sample_indices = np.arange(s0, s1)
        abs_time_ps = timestamp + sample_indices * dt_ns * 1000
        time_ns = sample_indices * dt_ns

        # 构建 segment
        segment = {
            "waveform": signal,
            "abs_time_ps": abs_time_ps,
            "dt": dt_ns,
            "record_id": record_id,
            "sample_start": s0,
            "sample_end": s1,
        }

        return {
            "merged_index": int(merged_index),
            "board": int(hm["board"]),
            "channel": int(hm["channel"]),
            "waveform": signal,
            "time_ns": time_ns,
            "abs_time_ps": abs_time_ps,
            "dt": dt_ns,
            "is_single_record": True,
            "segments": [segment],
        }

    def _extract_multi_record_waveform(self, merged_index: int, pad: int) -> dict:
        """从多个 record 提取波形（跨 record hit）"""
        hm = self._hit_merged[merged_index]

        # 通过索引获取 hit_indices（避免布尔筛选）
        hit_indices = self._merged_to_hit_idx.get(merged_index, [])
        if not hit_indices:
            # 没有 hit_merged_components，返回空
            return {
                "merged_index": int(merged_index),
                "board": int(hm["board"]),
                "channel": int(hm["channel"]),
                "waveform": np.array([], dtype=np.float32),
                "time_ns": np.array([], dtype=np.float32),
                "abs_time_ps": np.array([], dtype=np.int64),
                "dt": 0,
                "is_single_record": False,
                "segments": [],
            }

        hits = self._hit_threshold[hit_indices]

        # 收集所有片段
        segments = []
        for hit in hits:
            record_id = int(hit["record_id"])

            # 通过索引获取 record
            rec_idx = self._record_id_to_idx.get(record_id)
            if rec_idx is None:
                continue
            rec = self._records[rec_idx]

            edge_start = int(hit["edge_start"])
            edge_end = int(hit["edge_end"])

            dt_ns = int(rec["dt"])
            event_length = int(rec["event_length"])
            wave_offset = int(rec["wave_offset"])
            baseline = float(rec["baseline"])
            timestamp = int(rec["timestamp"])

            s0 = max(0, edge_start - pad)
            s1 = min(event_length, edge_end + pad)

            raw = self._wave_pool[wave_offset + s0 : wave_offset + s1].astype(np.float32)
            polarity = str(rec["polarity"]) if "polarity" in rec.dtype.names else "negative"
            signal = raw - baseline if polarity == "positive" else baseline - raw

            sample_indices = np.arange(s0, s1)
            abs_time_ps = timestamp + sample_indices * dt_ns * 1000

            segments.append(
                {
                    "waveform": signal,
                    "abs_time_ps": abs_time_ps,
                    "dt": dt_ns,
                    "record_id": record_id,
                    "sample_start": s0,
                    "sample_end": s1,
                }
            )

        if not segments:
            return {
                "merged_index": int(merged_index),
                "board": int(hm["board"]),
                "channel": int(hm["channel"]),
                "waveform": np.array([], dtype=np.float32),
                "time_ns": np.array([], dtype=np.float32),
                "abs_time_ps": np.array([], dtype=np.int64),
                "dt": 0,
                "is_single_record": False,
                "segments": [],
            }

        # 拼接所有片段（按时间排序）
        segments = sorted(segments, key=lambda x: x["abs_time_ps"][0])

        # 计算相对时间（基于第一个片段的起始时间）
        t0 = segments[0]["abs_time_ps"][0]

        waveforms = []
        times_ns = []
        abs_times_ps = []

        for seg in segments:
            waveforms.append(seg["waveform"])
            abs_times_ps.append(seg["abs_time_ps"])
            times_ns.append((seg["abs_time_ps"] - t0) / 1000.0)

        # 拼接
        concat_waveform = np.concatenate(waveforms)
        concat_time_ns = np.concatenate(times_ns)
        concat_abs_time_ps = np.concatenate(abs_times_ps)

        return {
            "merged_index": int(merged_index),
            "board": int(hm["board"]),
            "channel": int(hm["channel"]),
            "waveform": concat_waveform,
            "time_ns": concat_time_ns,
            "abs_time_ps": concat_abs_time_ps,
            "dt": segments[0]["dt"],
            "is_single_record": False,
            "segments": segments,
        }

    def get_peak_channel_data(
        self, peak_id: int, include_waveform: bool = False, pad: int = 30
    ) -> list[dict]:
        """
        获取 peak 的通道数据（特征 + 可选波形）

        参数
        ----
        peak_id : int
            Peak ID
        include_waveform : bool, default=False
            是否包含波形数据
        pad : int, default=30
            波形窗口 padding（仅当 include_waveform=True 时生效）

        返回
        ----
        list[dict]
            通道数据列表，每个 dict 包含：
            - 所有 get_peak_channels 返回的字段
            - 如果 include_waveform=True，额外包含：
                - waveform: np.ndarray
                - time_ns: np.ndarray
                - abs_time_ps: np.ndarray
                - dt: int
                - segments: list[dict]
        """
        # 获取特征
        channels = self.get_peak_channels(peak_id)

        if not include_waveform:
            return channels

        # 添加波形
        for ch in channels:
            merged_idx = ch["merged_index"]
            wf_data = self.get_channel_waveform(merged_idx, pad)

            # 合并波形数据
            ch["waveform"] = wf_data["waveform"]
            ch["time_ns"] = wf_data["time_ns"]
            ch["abs_time_ps"] = wf_data["abs_time_ps"]
            ch["dt"] = wf_data["dt"]
            ch["segments"] = wf_data["segments"]

        return channels

    def clear_waveform_cache(self, release_wave_pool: bool = False):
        """
        清理波形缓存

        参数
        ----
        release_wave_pool : bool, default=False
            是否释放 wave_pool（释放后需要重新加载才能访问波形）
        """
        # 清理波形缓存
        self._waveform_cache.clear()

        # 可选：释放波形层数据
        if release_wave_pool:
            self._records = None
            self._hit_threshold = None
            self._hit_merged_components = None
            self._wave_pool = None
            self._record_id_to_idx = None
            self._merged_to_hit_idx = None
            self._waveform_layer_loaded = False

    def get_sum_waveform(self, peak_id: int) -> dict | None:
        """
        获取 peak 的 sum waveform（从 peaklet_waveforms）

        参数
        ----
        peak_id : int
            Peak ID

        返回
        ----
        dict or None
            Sum waveform 数据，包含：
            - peak_id: int
            - waveform: np.ndarray
            - time_start: int (ps)
            - time_end: int (ps)
            - dt: int (ns)
            - time_ns: np.ndarray (相对时间)
        """
        # 加载 peaklet_waveforms
        try:
            peaklet_waveforms = self.context.get_data(self.run_id, "peaklet_waveforms")
            peaklet_waveform_pool = self.context.get_data(self.run_id, "peaklet_waveform_pool")
        except Exception:
            return None

        # 查找对应的 peaklet_waveform
        wf = peaklet_waveforms[peaklet_waveforms["peak_id"] == peak_id]
        if len(wf) == 0:
            return None

        wf = wf[0]
        wave_offset = int(wf["wave_offset"])
        wave_length = int(wf["wave_length"])
        dt = int(wf["dt"])
        time_start = int(wf["time_start"])
        time_end = int(wf["time_end"])

        # 提取波形
        waveform = peaklet_waveform_pool[wave_offset : wave_offset + wave_length]
        time_ns = np.arange(wave_length) * dt

        return {
            "peak_id": peak_id,
            "waveform": waveform,
            "time_start": time_start,
            "time_end": time_end,
            "dt": dt,
            "time_ns": time_ns,
        }

    # ========== 可视化方法 ==========

    def plot(
        self,
        peak_id: int,
        pad: int = 30,
        figsize: tuple[float, float] | None = None,
        show_sum: bool = True,
    ) -> tuple[Any | None, np.ndarray | None]:
        """
        绘制 peak 的所有通道波形

        参数
        ----
        peak_id : int
            Peak ID
        pad : int, default=30
            波形窗口 padding
        figsize : tuple or None
            图形尺寸 (width, height)，默认自动计算
        show_sum : bool, default=True
            是否显示 sum waveform（第一个子图）

        返回
        ----
        fig : matplotlib.figure.Figure or None
            图形对象
        axes : np.ndarray or None
            子图轴对象数组
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("plot() requires matplotlib. Install it with: pip install matplotlib")

        # 获取通道数据（包含波形）
        channels = self.get_peak_channel_data(peak_id, include_waveform=True, pad=pad)

        if not channels:
            print(f"No channels found for peak_id={peak_id}")
            return None, None

        # 获取 sum waveform
        sum_data = None
        if show_sum:
            sum_data = self.get_sum_waveform(peak_id)

        # 计算图形尺寸
        n_channels = len(channels)
        n_subplots = n_channels + (1 if show_sum and sum_data else 0)

        if figsize is None:
            figsize = (16, max(7, 0.8 * n_channels + 3.0))

        # 创建子图
        height_ratios = [2.5] + [1] * n_channels if show_sum and sum_data else [1] * n_channels
        fig, axes = plt.subplots(
            n_subplots,
            1,
            figsize=figsize,
            sharex=False,
            squeeze=False,
            gridspec_kw={"height_ratios": height_ratios},
        )
        axes = axes.flatten()

        ax_offset = 0

        # 计算全局时间范围（用于对齐 x 轴）
        event_t0 = min(ch["abs_time_ps"][0] for ch in channels if len(ch["abs_time_ps"]) > 0)
        t_min = float("inf")
        t_max = float("-inf")

        # 为每个通道计算相对时间
        for ch in channels:
            if len(ch["abs_time_ps"]) > 0:
                ch["relative_time_ns"] = (ch["abs_time_ps"] - event_t0) / 1000.0
                t_min = min(t_min, ch["relative_time_ns"][0])
                t_max = max(t_max, ch["relative_time_ns"][-1])

        # 绘制 sum waveform（需要对齐到 event_t0）
        if show_sum and sum_data:
            ax_sum = axes[0]
            # 将 sum waveform 的时间对齐到 event_t0
            sum_time_aligned = (sum_data["time_start"] - event_t0) / 1000.0 + sum_data["time_ns"]
            ax_sum.plot(sum_time_aligned, sum_data["waveform"], "k-", lw=1.5)
            ax_sum.set_title(f"Peak {peak_id} - Sum Waveform (from peaklet)")
            ax_sum.set_ylabel("Sum Signal")
            ax_sum.grid(True, alpha=0.3)

            # 更新时间范围
            t_min = min(t_min, sum_time_aligned[0])
            t_max = max(t_max, sum_time_aligned[-1])

            ax_offset = 1

        # 绘制各通道波形
        cmap = plt.get_cmap("tab10")
        for i, ch in enumerate(channels):
            ax = axes[ax_offset + i]
            color = cmap(i % 10)

            # 绘制波形
            if len(ch["waveform"]) > 0:
                ax.plot(ch["relative_time_ns"], ch["waveform"], color=color, lw=1.2)

                # 标记 hit 窗口（如果有多个 segment）
                if len(ch["segments"]) > 1:
                    for seg in ch["segments"]:
                        seg_time_ns = (seg["abs_time_ps"] - event_t0) / 1000.0
                        ax.axvspan(
                            seg_time_ns[0],
                            seg_time_ns[-1],
                            color=color,
                            alpha=0.15,
                        )

            # 标题和标签
            label = f"Board {ch['board']}, Ch {ch['channel']}"
            ax.set_ylabel(label)
            ax.grid(True, alpha=0.3)

            # 添加特征信息
            info_text = (
                f"Area: {ch['area']:.1f}, "
                f"Height: {ch['height']:.1f}, "
                f"Width: {ch['width']:.1f} ns"
            )
            ax.text(
                0.02,
                0.95,
                info_text,
                transform=ax.transAxes,
                fontsize=8,
                verticalalignment="top",
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.7},
            )

        # 设置 x 轴
        axes[-1].set_xlabel("Time from event start (ns)")
        if t_min != float("inf") and t_max != float("-inf"):
            for ax in axes:
                ax.set_xlim(t_min, t_max)

        plt.tight_layout()
        return fig, axes

    def batch_plot(
        self,
        peak_ids: list[int],
        output_dir: str = "output",
        pad: int = 30,
        show_sum: bool = True,
    ):
        """
        批量绘制多个 peak

        参数
        ----
        peak_ids : list[int]
            Peak ID 列表
        output_dir : str, default="output"
            输出目录
        pad : int, default=30
            波形窗口 padding
        show_sum : bool, default=True
            是否显示 sum waveform
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "batch_plot() requires matplotlib. Install it with: pip install matplotlib"
            )

        from pathlib import Path

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        for peak_id in peak_ids:
            print(f"Plotting peak {peak_id}...")
            fig, axes = self.plot(peak_id, pad=pad, show_sum=show_sum)

            if fig:
                save_path = Path(output_dir) / f"peak_{peak_id}.png"
                fig.savefig(save_path, dpi=150, bbox_inches="tight")
                plt.close(fig)
                print(f"  Saved to {save_path}")

    def plot_channel_comparison(
        self,
        peak_id: int,
        channel_selector=None,
        pad: int = 30,
        figsize: tuple[float, float] = (14, 8),
    ) -> tuple[Any | None, Any | None]:
        """
        在同一个图上叠加显示多个通道（用于对比）

        参数
        ----
        peak_id : int
            Peak ID
        channel_selector : callable or None
            通道筛选函数，接受 channel dict，返回 bool
            例如：lambda ch: ch['area'] > 100
        pad : int, default=30
            波形窗口 padding
        figsize : tuple
            图形尺寸

        返回
        ----
        fig : matplotlib.figure.Figure or None
        ax : matplotlib.axes.Axes or None
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "plot_channel_comparison() requires matplotlib. "
                "Install it with: pip install matplotlib"
            )

        # 获取通道数据
        channels = self.get_peak_channel_data(peak_id, include_waveform=True, pad=pad)

        if not channels:
            print(f"No channels found for peak_id={peak_id}")
            return None, None

        # 应用筛选
        if channel_selector:
            channels = [ch for ch in channels if channel_selector(ch)]

        if not channels:
            print(f"No channels match the selector for peak_id={peak_id}")
            return None, None

        # 创建图形
        fig, ax = plt.subplots(figsize=figsize)

        # 计算全局时间基准
        event_t0 = min(ch["abs_time_ps"][0] for ch in channels if len(ch["abs_time_ps"]) > 0)

        # 绘制各通道
        cmap = plt.get_cmap("tab10")
        for i, ch in enumerate(channels):
            if len(ch["waveform"]) == 0:
                continue

            color = cmap(i % 10)
            relative_time_ns = (ch["abs_time_ps"] - event_t0) / 1000.0

            label = f"B{ch['board']}:Ch{ch['channel']} (A={ch['area']:.0f})"
            ax.plot(relative_time_ns, ch["waveform"], color=color, lw=1.5, label=label, alpha=0.8)

        ax.set_xlabel("Time from event start (ns)")
        ax.set_ylabel("Signal")
        ax.set_title(f"Peak {peak_id} - Channel Comparison")
        ax.legend(loc="best", framealpha=0.9)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig, ax

    def plot_sum_vs_channels(
        self,
        peak_id: int,
        pad: int = 30,
        figsize: tuple[float, float] = (14, 10),
    ) -> tuple[Any | None, np.ndarray | None]:
        """
        对比绘制 sum waveform 与各通道叠加

        上图：sum waveform
        下图：所有通道叠加显示

        参数
        ----
        peak_id : int
            Peak ID
        pad : int, default=30
            波形窗口 padding
        figsize : tuple
            图形尺寸

        返回
        ----
        fig : matplotlib.figure.Figure or None
        axes : np.ndarray or None
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "plot_sum_vs_channels() requires matplotlib. "
                "Install it with: pip install matplotlib"
            )

        # 获取数据
        channels = self.get_peak_channel_data(peak_id, include_waveform=True, pad=pad)
        sum_data = self.get_sum_waveform(peak_id)

        if not channels or not sum_data:
            print(f"No data found for peak_id={peak_id}")
            return None, None

        # 创建图形
        fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=True)

        # 计算全局时间基准
        event_t0 = min(ch["abs_time_ps"][0] for ch in channels if len(ch["abs_time_ps"]) > 0)

        # 上图：sum waveform
        ax_sum = axes[0]
        sum_time_ns = (sum_data["time_start"] - event_t0) / 1000.0 + sum_data["time_ns"]
        ax_sum.plot(sum_time_ns, sum_data["waveform"], "k-", lw=2, label="Sum")
        ax_sum.set_ylabel("Sum Signal")
        ax_sum.set_title(f"Peak {peak_id} - Sum Waveform")
        ax_sum.legend(loc="upper right")
        ax_sum.grid(True, alpha=0.3)

        # 下图：各通道叠加
        ax_channels = axes[1]
        cmap = plt.get_cmap("tab10")
        for i, ch in enumerate(channels):
            if len(ch["waveform"]) == 0:
                continue

            color = cmap(i % 10)
            relative_time_ns = (ch["abs_time_ps"] - event_t0) / 1000.0

            label = f"B{ch['board']}:Ch{ch['channel']}"
            ax_channels.plot(
                relative_time_ns, ch["waveform"], color=color, lw=1.2, label=label, alpha=0.7
            )

        ax_channels.set_xlabel("Time from event start (ns)")
        ax_channels.set_ylabel("Channel Signal")
        ax_channels.set_title("Individual Channels (overlaid)")
        ax_channels.legend(loc="upper right", ncol=2, framealpha=0.9)
        ax_channels.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig, axes
