"""
S1-S2 配对数据访问器

职责：
- 读取并缓存 S1-S2 pair 数据
- 按 pair_id、s1_peak_id、s2_peak_id 快速查询
- 提供基础过滤（drift_time, log10_s2_s1, score, flags）
- 按需加载 sum waveform
- 提供最小必要的单 pair 可视化

设计原则：
- 职责明确：只做数据访问，不做复杂分析
- 接口稳定：返回 numpy structured array
- 性能优先：波形层默认懒加载，查询使用索引
- 时间安全：所有时间统一为 ns

使用示例：
    >>> from waveform_analysis.utils import S1S2PairAccessor
    >>>
    >>> # 创建访问器
    >>> accessor = S1S2PairAccessor(context, run_id="run_001")
    >>>
    >>> # 查询单个配对
    >>> pair = accessor.get_pair(pair_id=42)
    >>> print(f"Drift time: {pair['drift_time_ns']:.1f} ns")
    >>>
    >>> # 查询某个 S1 的所有配对
    >>> pairs_for_s1 = accessor.get_pairs_for_s1(s1_peak_id=10)
    >>>
    >>> # 过滤配对
    >>> mask = accessor.build_mask(
    ...     drift_time_ns_range=(10000, 50000),
    ...     log10_s2_s1_range=(1.5, None),
    ... )
    >>> filtered = accessor.pairs[mask]
    >>>
    >>> # 绘制单个配对
    >>> fig, ax = accessor.plot_pair(pair_id=42)
"""

from typing import Any

import numpy as np


class WaveformNotFoundError(Exception):
    """波形未找到异常"""

    pass


class S1S2PairAccessor:
    """S1-S2 配对数据访问器（第一版：核心功能）

    核心职责：
    - 读取并缓存 S1-S2 pair 数据
    - 按 pair_id、s1_peak_id、s2_peak_id 快速查询
    - 提供基础过滤（drift_time, log10_s2_s1, score, flags）
    - 按需加载 sum waveform
    - 提供最小必要的单 pair 可视化

    不包含（放到后续版本或独立 analysis helper）：
    - 统计分析（score distribution, ambiguity analysis）
    - 批量绘图
    - 多维 cut scan
    """

    def __init__(
        self,
        context: Any,
        run_id: str,
        source: str = "pairs",
        selected_only: bool = False,
        lazy_pairs: bool = False,
        lazy_waveform: bool = True,
    ):
        """初始化访问器

        参数
        ----
        context : Context
            DAQAnalyzer 的 context 对象
        run_id : str
            Run ID
        source : str, default="pairs"
            数据源选择：
            - "pairs": 使用 s1_s2_pairs（最终选择结果）
            - "candidates": 使用 s1_s2_pair_candidates（所有候选）
        selected_only : bool, default=False
            是否只保留 selected=True 的配对
            （如果数据中没有 selected 字段，则忽略此筛选）
        lazy_pairs : bool, default=False
            是否延迟加载 pair table
        lazy_waveform : bool, default=True
            是否延迟加载 waveform layer（推荐 True）
        """
        self.context = context
        self.run_id = run_id
        self.source = source
        self.selected_only = selected_only

        # Pair 数据层
        self._pairs = None
        self._pair_id_to_idx = None
        self._s1_to_indices = None
        self._s2_to_indices = None

        # 波形层（延迟加载）
        self._peaklet_waveforms = None
        self._peaklet_waveform_pool = None
        self._peak_id_to_wf_idx = None
        self._waveform_cache = {}

        # 标志
        self._pairs_loaded = False
        self._waveform_layer_loaded = False

        # 加载 pair 数据（除非 lazy_pairs=True）
        if not lazy_pairs:
            self._load_pairs()

    def _load_pairs(self):
        """加载 pair 数据并构建索引"""
        if self._pairs_loaded:
            return

        # 根据 source 选择数据键名
        if self.source == "pairs":
            data_key = "s1_s2_pairs"
        elif self.source == "candidates":
            data_key = "s1_s2_pair_candidates"
        else:
            raise ValueError(f"Invalid source '{self.source}'. Must be 'pairs' or 'candidates'.")

        # 加载数据
        self._pairs = self.context.get_data(self.run_id, data_key)

        # 应用 selected_only 筛选
        if self.selected_only:
            if "selected" in self._pairs.dtype.names:
                self._pairs = self._pairs[self._pairs["selected"]]
            # 如果没有 selected 字段，忽略筛选（不报错）

        # 构建索引
        self._build_indices()

        self._pairs_loaded = True

    def _build_indices(self):
        """构建索引（存储 row indices 而不是 pair_id）"""
        pairs = self._pairs

        # pair_id 到索引的映射（1对1）
        self._pair_id_to_idx = {int(p["pair_id"]): i for i, p in enumerate(pairs)}

        # s1_peak_id 到 row indices 的映射（1对多）
        self._s1_to_indices = {}
        for i, pair in enumerate(pairs):
            s1_id = int(pair["s1_peak_id"])
            if s1_id not in self._s1_to_indices:
                self._s1_to_indices[s1_id] = []
            self._s1_to_indices[s1_id].append(i)

        # 转换为 numpy array
        for s1_id in self._s1_to_indices:
            self._s1_to_indices[s1_id] = np.array(self._s1_to_indices[s1_id], dtype=np.int64)

        # s2_peak_id 到 row indices 的映射（同样处理）
        self._s2_to_indices = {}
        for i, pair in enumerate(pairs):
            s2_id = int(pair["s2_peak_id"])
            if s2_id not in self._s2_to_indices:
                self._s2_to_indices[s2_id] = []
            self._s2_to_indices[s2_id].append(i)

        for s2_id in self._s2_to_indices:
            self._s2_to_indices[s2_id] = np.array(self._s2_to_indices[s2_id], dtype=np.int64)

    @property
    def pairs(self) -> np.ndarray:
        """直接访问所有配对数据（numpy structured array）

        返回
        ----
        np.ndarray
            配对数据（structured array）
        """
        if not self._pairs_loaded:
            self._load_pairs()
        return self._pairs

    def get_pair(self, pair_id: int) -> np.void | None:
        """获取单个配对的完整信息（返回 structured row）

        参数
        ----
        pair_id : int
            配对 ID

        返回
        ----
        np.void or None
            配对的 structured row，包含所有字段
        """
        if not self._pairs_loaded:
            self._load_pairs()

        idx = self._pair_id_to_idx.get(pair_id)
        if idx is None:
            return None

        return self._pairs[idx]

    def get_pairs_for_s1(self, s1_peak_id: int) -> np.ndarray:
        """获取给定 S1 的所有配对（返回 structured array）

        参数
        ----
        s1_peak_id : int
            S1 peak ID

        返回
        ----
        np.ndarray
            配对数据（structured array），如果没有找到则返回空数组
        """
        if not self._pairs_loaded:
            self._load_pairs()

        indices = self._s1_to_indices.get(s1_peak_id)
        if indices is None or len(indices) == 0:
            # 返回空数组（保留 dtype）
            return np.array([], dtype=self._pairs.dtype)

        return self._pairs[indices]

    def get_pairs_for_s2(self, s2_peak_id: int) -> np.ndarray:
        """获取给定 S2 的所有配对（返回 structured array）

        参数
        ----
        s2_peak_id : int
            S2 peak ID

        返回
        ----
        np.ndarray
            配对数据（structured array），如果没有找到则返回空数组
        """
        if not self._pairs_loaded:
            self._load_pairs()

        indices = self._s2_to_indices.get(s2_peak_id)
        if indices is None or len(indices) == 0:
            # 返回空数组（保留 dtype）
            return np.array([], dtype=self._pairs.dtype)

        return self._pairs[indices]

    def build_mask(
        self,
        drift_time_ns_range: tuple[float, float] | None = None,
        log10_s2_s1_range: tuple[float, float] | None = None,
        score_total_range: tuple[float, float] | None = None,
        flags_any: int | None = None,
        flags_all: int | None = None,
        flags_none: int | None = None,
        selected: bool | None = None,
        custom_filter: Any = None,
    ) -> np.ndarray:
        """构建过滤 mask（返回布尔数组）

        参数
        ----
        drift_time_ns_range : tuple or None
            漂移时间范围 (min_ns, max_ns)，None 表示不限
        log10_s2_s1_range : tuple or None
            log10(S2/S1) 范围 (min, max)，None 表示不限
        score_total_range : tuple or None
            总分范围 (min, max)，None 表示不限
        flags_any : int or None
            满足任一标志位：(flags & flags_any) != 0
        flags_all : int or None
            满足所有标志位：(flags & flags_all) == flags_all
        flags_none : int or None
            不满足任何标志位：(flags & flags_none) == 0
        selected : bool or None
            是否筛选 selected 字段（仅当字段存在时有效）
        custom_filter : callable or None
            自定义过滤函数，接受 structured array，返回布尔数组

        返回
        ----
        np.ndarray
            布尔数组，True 表示满足条件

        使用示例
        --------
        >>> mask = accessor.build_mask(
        ...     drift_time_ns_range=(10000, 50000),
        ...     log10_s2_s1_range=(1.5, None),
        ... )
        >>> filtered_pairs = accessor.pairs[mask]
        """
        if not self._pairs_loaded:
            self._load_pairs()

        pairs = self._pairs
        mask = np.ones(len(pairs), dtype=bool)

        # drift_time_ns 范围筛选
        if drift_time_ns_range is not None:
            min_drift, max_drift = drift_time_ns_range
            if min_drift is not None:
                mask &= pairs["drift_time_ns"] >= min_drift
            if max_drift is not None:
                mask &= pairs["drift_time_ns"] <= max_drift

        # log10_s2_s1 范围筛选
        if log10_s2_s1_range is not None:
            min_ratio, max_ratio = log10_s2_s1_range
            if min_ratio is not None:
                mask &= pairs["log10_s2_s1"] >= min_ratio
            if max_ratio is not None:
                mask &= pairs["log10_s2_s1"] <= max_ratio

        # score_total 范围筛选
        if score_total_range is not None and "score_total" in pairs.dtype.names:
            min_score, max_score = score_total_range
            if min_score is not None:
                mask &= pairs["score_total"] >= min_score
            if max_score is not None:
                mask &= pairs["score_total"] <= max_score

        # flags 筛选
        if "flags" in pairs.dtype.names:
            if flags_any is not None:
                mask &= (pairs["flags"] & flags_any) != 0
            if flags_all is not None:
                mask &= (pairs["flags"] & flags_all) == flags_all
            if flags_none is not None:
                mask &= (pairs["flags"] & flags_none) == 0

        # selected 筛选
        if selected is not None and "selected" in pairs.dtype.names:
            mask &= pairs["selected"] == selected

        # 自定义过滤
        if custom_filter is not None:
            custom_mask = custom_filter(pairs)
            mask &= custom_mask

        return mask

    def filter_pairs(self, **kwargs) -> np.ndarray:
        """快捷方法：直接返回过滤后的 pairs

        等价于：accessor.pairs[accessor.build_mask(**kwargs)]

        参数
        ----
        **kwargs
            传递给 build_mask() 的参数

        返回
        ----
        np.ndarray
            过滤后的配对数据（structured array）
        """
        mask = self.build_mask(**kwargs)
        return self.pairs[mask]

    # ========== 波形层方法 ==========

    def _load_waveform_layer(self):
        """延迟加载波形层数据"""
        if self._waveform_layer_loaded:
            return

        # 加载 peaklet waveforms
        self._peaklet_waveforms = self.context.get_data(self.run_id, "peaklet_waveforms")
        self._peaklet_waveform_pool = self.context.get_data(self.run_id, "peaklet_waveform_pool")

        # 构建 peak_id 到 waveform 索引的映射
        self._peak_id_to_wf_idx = {
            int(wf["peak_id"]): i for i, wf in enumerate(self._peaklet_waveforms)
        }

        self._waveform_layer_loaded = True

    def _normalize_waveform_time(self, wf_row) -> tuple[float, float, np.ndarray]:
        """归一化波形时间到 ns（统一单位）

        参数
        ----
        wf_row
            peaklet_waveforms 的一行

        返回
        ----
        (time_start_ns, dt_ns, time_rel_ns)
        """
        # 检查 dt 字段（可能是 dt 或 dt_ps）
        names = wf_row.dtype.names
        if "dt_ps" in names:
            dt_ns = float(wf_row["dt_ps"]) / 1000.0
        elif "dt" in names:
            # 项目约定：peaklet_waveforms 的 dt 单位为 ns
            dt_ns = float(wf_row["dt"])
        else:
            raise ValueError("wf_row 缺少 dt 或 dt_ps 字段")

        # time_start 单位为 ps
        time_start_ps = int(wf_row["time_start"])
        time_start_ns = time_start_ps / 1000.0

        # 计算相对时间（相对于 waveform 自身起点）
        wave_length = int(wf_row["wave_length"])
        time_rel_ns = np.arange(wave_length) * dt_ns

        return time_start_ns, dt_ns, time_rel_ns

    def get_waveform(self, peak_id: int, copy: bool = False) -> dict | None:
        """获取 peak 的 sum waveform（延迟加载波形层）

        参数
        ----
        peak_id : int
            Peak ID
        copy : bool, default=False
            是否返回 waveform 的 copy（默认返回 view）

        返回
        ----
        dict or None:
            - peak_id: int
            - waveform: np.ndarray（view 或 copy）
            - time_start_ns: float（绝对起始时间，ns）
            - time_rel_ns: np.ndarray（相对时间，ns）
            - dt_ns: float（采样间隔，ns）

        注意
        ----
        - 默认返回 waveform 的 view，不应原地修改
        - 需要修改时设置 copy=True
        - 所有时间单位统一为 ns
        """
        # 延迟加载波形层
        if not self._waveform_layer_loaded:
            self._load_waveform_layer()

        # 检查缓存
        if peak_id in self._waveform_cache:
            cached = self._waveform_cache[peak_id]
            if copy:
                return {**cached, "waveform": cached["waveform"].copy()}
            return cached

        # 从 peaklet_waveforms 查找
        idx = self._peak_id_to_wf_idx.get(peak_id)
        if idx is None:
            return None

        wf = self._peaklet_waveforms[idx]
        wave_offset = int(wf["wave_offset"])
        wave_length = int(wf["wave_length"])

        # 提取波形（默认返回 view）
        waveform = self._peaklet_waveform_pool[wave_offset : wave_offset + wave_length]

        # 归一化时间到 ns
        time_start_ns, dt_ns, time_rel_ns = self._normalize_waveform_time(wf)

        result = {
            "peak_id": peak_id,
            "waveform": waveform.copy() if copy else waveform,
            "time_start_ns": time_start_ns,
            "time_rel_ns": time_rel_ns,
            "dt_ns": dt_ns,
        }

        # 缓存（缓存的是 view）
        if not copy:
            self._waveform_cache[peak_id] = result

        return result

    def get_pair_waveforms(
        self,
        pair_or_id,
        copy: bool = False,
        missing: str = "raise",
    ) -> tuple[dict, dict] | None:
        """获取配对的 S1 和 S2 波形

        参数
        ----
        pair_or_id : int or np.void
            pair_id（int）或 pair row（structured row）
        copy : bool, default=False
            是否返回 waveform 的 copy
        missing : str, default="raise"
            缺失波形时的行为：
            - "raise": 抛出 WaveformNotFoundError
            - "return_none": 返回 None

        返回
        ----
        (s1_waveform, s2_waveform) or None

        异常
        ----
        WaveformNotFoundError
            当 missing="raise" 且找不到波形时抛出
        """
        # 获取配对信息
        if isinstance(pair_or_id, int | np.integer):
            pair = self.get_pair(pair_or_id)
            if pair is None:
                if missing == "raise":
                    raise ValueError(f"Pair {pair_or_id} not found")
                return None
        else:
            pair = pair_or_id

        # 获取 S1 和 S2 波形
        s1_peak_id = int(pair["s1_peak_id"])
        s2_peak_id = int(pair["s2_peak_id"])

        s1_wf = self.get_waveform(s1_peak_id, copy=copy)
        s2_wf = self.get_waveform(s2_peak_id, copy=copy)

        # 检查缺失
        if s1_wf is None:
            if missing == "raise":
                raise WaveformNotFoundError(f"Missing waveform for s1_peak_id={s1_peak_id}")
            return None

        if s2_wf is None:
            if missing == "raise":
                raise WaveformNotFoundError(f"Missing waveform for s2_peak_id={s2_peak_id}")
            return None

        return s1_wf, s2_wf

    def clear_waveform_cache(self):
        """清理已提取的 waveform 缓存

        保留 peaklet_waveforms 和 peaklet_waveform_pool
        """
        self._waveform_cache.clear()

    def release_waveform_layer(self):
        """释放整个波形层（包括缓存和原始数据）

        释放后需要重新调用波形方法才会重新加载
        """
        self._peaklet_waveforms = None
        self._peaklet_waveform_pool = None
        self._peak_id_to_wf_idx = None
        self._waveform_cache.clear()
        self._waveform_layer_loaded = False

    # ========== 可视化方法 ==========

    def plot_pair(
        self,
        pair_or_id,
        pad_ns: float = 200,
        show_info: bool = True,
        ax=None,
    ):
        """在统一时间轴上绘制 S1-S2 配对波形

        参数
        ----
        pair_or_id : int or np.void
            pair_id（int）或 pair row（structured row）
        pad_ns : float, default=200
            在波形两端扩展的时间范围（ns）
        show_info : bool, default=True
            是否在标题中显示关键信息
        ax : matplotlib.axes.Axes or None
            目标 axes，None 时创建新 figure

        返回
        ----
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes

        显示信息
        --------
        标题包含：
        - pair_id, s1_peak_id, s2_peak_id
        - drift_time_us（微秒，更直观）
        - s1_area, s2_area
        - log10_s2_s1
        - score_total
        - rank_for_s1, rank_for_s2
        - selected

        特点
        ----
        - S1 起点作为时间零点
        - S1 和 S2 波形叠加在同一图上
        - 垂直虚线标记 S1 和 S2 起点
        - 不强制 plt.show()，由用户控制
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "plot_pair() requires matplotlib. Install it with: pip install matplotlib"
            )

        # 获取配对信息
        if isinstance(pair_or_id, int | np.integer):
            pair = self.get_pair(pair_or_id)
            if pair is None:
                raise ValueError(f"Pair {pair_or_id} not found")
        else:
            pair = pair_or_id

        # 获取波形
        s1_wf = self.get_waveform(int(pair["s1_peak_id"]), copy=False)
        s2_wf = self.get_waveform(int(pair["s2_peak_id"]), copy=False)

        if s1_wf is None:
            raise WaveformNotFoundError(f"Missing waveform for s1_peak_id={pair['s1_peak_id']}")
        if s2_wf is None:
            raise WaveformNotFoundError(f"Missing waveform for s2_peak_id={pair['s2_peak_id']}")

        # 创建 figure/axes
        if ax is None:
            fig, ax = plt.subplots(figsize=(14, 4))
        else:
            fig = ax.get_figure()

        # 统一时间轴：以 S1 起点为 0
        event_t0_ns = s1_wf["time_start_ns"]

        # S1 相对时间
        s1_time_rel = (s1_wf["time_start_ns"] - event_t0_ns) + s1_wf["time_rel_ns"]

        # S2 相对时间
        s2_time_rel = (s2_wf["time_start_ns"] - event_t0_ns) + s2_wf["time_rel_ns"]

        # 绘制波形
        ax.plot(
            s1_time_rel,
            s1_wf["waveform"],
            color="tab:blue",
            lw=1.5,
            label=f"S1 (peak_id={pair['s1_peak_id']})",
        )
        ax.plot(
            s2_time_rel,
            s2_wf["waveform"],
            color="tab:orange",
            lw=1.5,
            label=f"S2 (peak_id={pair['s2_peak_id']})",
        )

        # 标记起点
        ax.axvline(s1_time_rel[0], color="tab:blue", ls="--", alpha=0.4)
        ax.axvline(s2_time_rel[0], color="tab:orange", ls="--", alpha=0.4)

        # 设置范围
        t_min = min(s1_time_rel[0], s2_time_rel[0]) - pad_ns
        t_max = max(s1_time_rel[-1], s2_time_rel[-1]) + pad_ns
        ax.set_xlim(t_min, t_max)

        # 标签和标题
        ax.set_xlabel("Time from S1 start (ns)")
        ax.set_ylabel("Amplitude (summed signal)")

        if show_info:
            # 提取关键信息
            pair_id = int(pair["pair_id"])
            s1_peak_id = int(pair["s1_peak_id"])
            s2_peak_id = int(pair["s2_peak_id"])
            drift_time_us = float(pair["drift_time_ns"]) / 1000.0  # 转为微秒
            s1_area = float(pair["s1_area"])
            s2_area = float(pair["s2_area"])
            log10_s2_s1 = float(pair["log10_s2_s1"])

            # 可选字段（可能不存在）
            names = pair.dtype.names
            score_total = float(pair["score_total"]) if "score_total" in names else None
            rank_for_s1 = int(pair["rank_for_s1"]) if "rank_for_s1" in names else None
            rank_for_s2 = int(pair["rank_for_s2"]) if "rank_for_s2" in names else None
            selected = bool(pair["selected"]) if "selected" in names else None

            # 构建标题
            title_parts = [
                f"Pair {pair_id} | S1={s1_peak_id}, S2={s2_peak_id}",
                f"Drift={drift_time_us:.2f} μs",
                f"S1_area={s1_area:.0f}, S2_area={s2_area:.0f}",
                f"log10(S2/S1)={log10_s2_s1:.2f}",
            ]

            if score_total is not None:
                title_parts.append(f"Score={score_total:.2f}")
            if rank_for_s1 is not None and rank_for_s2 is not None:
                title_parts.append(f"Rank(S1)={rank_for_s1}, Rank(S2)={rank_for_s2}")
            if selected is not None:
                title_parts.append(f"Selected={selected}")

            ax.set_title(" | ".join(title_parts), fontsize=10)

        ax.grid(True, alpha=0.3)
        ax.legend()
        plt.tight_layout()

        return fig, ax
