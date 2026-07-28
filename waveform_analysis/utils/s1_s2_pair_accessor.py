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
    >>> pair = accessor.pair(pair_id=42)
    >>> print(f"Drift time: {pair['drift_time_ns']:.1f} ns")
    >>>
    >>> # 查询某个 S1 的所有配对
    >>> pairs_for_s1 = accessor.pairs_for_s1(s1_peak_id=10)
    >>>
    >>> # 过滤配对
    >>> mask = accessor.mask(
    ...     drift_time_ns_range=(10000, 50000),
    ...     log10_s2_s1_range=(1.5, None),
    ... )
    >>> filtered = accessor.pairs[mask]
    >>>
    >>> # 绘制单个配对
    >>> fig, ax = accessor.plot(pair_id=42)
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
            - "events": 使用 events（完整事件重建结果）
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
        self._pairs: np.ndarray | None = None
        self._pair_id_to_idx: dict[int, int] | None = None
        self._s1_to_indices: dict[int, np.ndarray] | None = None
        self._s2_to_indices: dict[int, np.ndarray] | None = None

        # 波形层（延迟加载）
        self._peaklet_waveforms: np.ndarray | None = None
        self._peaklet_waveform_pool: np.ndarray | None = None
        self._peak_id_to_wf_idx: dict[int, int] | None = None
        self._waveform_cache: dict[int, dict] = {}

        # 标志
        self._pairs_loaded = False
        self._waveform_layer_loaded = False

        # 加载 pair 数据（除非 lazy_pairs=True）
        if not lazy_pairs:
            self._load_pairs()

    # ========== 数据加载 ==========

    def _load_pairs(self) -> None:
        """加载 pair 数据并构建索引"""
        if self._pairs_loaded:
            return

        # 根据 source 选择数据键名
        if self.source == "pairs":
            data_key = "s1_s2_pairs"
        elif self.source == "candidates":
            data_key = "s1_s2_pair_candidates"
        elif self.source == "events":
            data_key = "events"
        else:
            raise ValueError(
                f"Invalid source '{self.source}'. Must be 'pairs', 'candidates', or 'events'."
            )

        # 加载数据
        pairs = self.context.get_data(self.run_id, data_key)

        # 应用 selected_only 筛选
        if self.selected_only:
            if "selected" in pairs.dtype.names:
                pairs = pairs[pairs["selected"]]
            # 如果没有 selected 字段，忽略筛选（不报错）

        self._pairs = pairs

        # 构建索引
        self._build_indices()

        self._pairs_loaded = True

    def _build_indices(self) -> None:
        """构建索引（存储 row indices 而不是 pair_id）"""
        assert self._pairs is not None, "_load_pairs must be called first"

        # pair_id 到索引的映射（1对1）
        self._pair_id_to_idx = {int(p["pair_id"]): i for i, p in enumerate(self._pairs)}

        # s1_peak_id 到 row indices 的映射（1对多）
        self._s1_to_indices = self._build_one_to_many_index(self._pairs, "s1_peak_id")

        # s2_peak_id 到 row indices 的映射（1对多）
        self._s2_to_indices = self._build_one_to_many_index(self._pairs, "s2_peak_id")

    @staticmethod
    def _build_one_to_many_index(pairs: np.ndarray, field_name: str) -> dict[int, np.ndarray]:
        """构建 1对多 索引：field 值 -> row indices (int64 array)"""
        index: dict[int, list[int]] = {}
        for i, pair in enumerate(pairs):
            key = int(pair[field_name])
            index.setdefault(key, []).append(i)
        return {k: np.array(v, dtype=np.int64) for k, v in index.items()}

    # ========== 属性访问 ==========

    @property
    def pairs(self) -> np.ndarray:
        """直接访问所有配对数据（numpy structured array）"""
        if not self._pairs_loaded:
            self._load_pairs()
        assert self._pairs is not None
        return self._pairs

    # ========== 单 pair 查询 ==========

    def pair(self, pair_id: int) -> np.void | None:
        """获取单个配对的完整信息（返回 structured row）"""
        if not self._pairs_loaded:
            self._load_pairs()
        assert self._pair_id_to_idx is not None

        idx = self._pair_id_to_idx.get(pair_id)
        if idx is None:
            return None

        assert self._pairs is not None
        return self._pairs[idx]

    def pairs_for_s1(self, s1_peak_id: int) -> np.ndarray:
        """获取给定 S1 的所有配对（返回 structured array）"""
        if not self._pairs_loaded:
            self._load_pairs()
        assert self._s1_to_indices is not None

        indices = self._s1_to_indices.get(s1_peak_id)
        if indices is None or len(indices) == 0:
            assert self._pairs is not None
            return np.array([], dtype=self._pairs.dtype)

        assert self._pairs is not None
        return self._pairs[indices]

    def pairs_for_s2(self, s2_peak_id: int) -> np.ndarray:
        """获取给定 S2 的所有配对（返回 structured array）"""
        if not self._pairs_loaded:
            self._load_pairs()
        assert self._s2_to_indices is not None

        indices = self._s2_to_indices.get(s2_peak_id)
        if indices is None or len(indices) == 0:
            assert self._pairs is not None
            return np.array([], dtype=self._pairs.dtype)

        assert self._pairs is not None
        return self._pairs[indices]

    # ========== 筛选 ==========

    def mask(
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
        """构建过滤 mask（返回布尔数组）"""
        if not self._pairs_loaded:
            self._load_pairs()
        assert self._pairs is not None

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

    # ========== 波形层方法 ==========

    def _load_waveform_layer(self) -> None:
        """延迟加载波形层数据"""
        if self._waveform_layer_loaded:
            return

        self._peaklet_waveforms = self.context.get_data(self.run_id, "peaklet_waveforms")
        self._peaklet_waveform_pool = self.context.get_data(self.run_id, "peaklet_waveform_pool")

        assert self._peaklet_waveforms is not None
        self._peak_id_to_wf_idx = {
            int(wf["peak_id"]): i for i, wf in enumerate(self._peaklet_waveforms)
        }

        self._waveform_layer_loaded = True

    def _normalize_waveform_time(self, wf_row: np.void) -> tuple[float, float, np.ndarray]:
        """归一化波形时间到 ns（统一单位）"""
        names = wf_row.dtype.names
        if "dt_ps" in names:
            dt_ns = float(wf_row["dt_ps"]) / 1000.0
        elif "dt" in names:
            dt_ns = float(wf_row["dt"])
        else:
            raise ValueError("wf_row 缺少 dt 或 dt_ps 字段")

        time_start_ps = int(wf_row["time_start"])
        time_start_ns = time_start_ps / 1000.0

        wave_length = int(wf_row["wave_length"])
        time_rel_ns = np.arange(wave_length) * dt_ns

        return time_start_ns, dt_ns, time_rel_ns

    def waveform(self, peak_id: int, copy: bool = False) -> dict | None:
        """获取 peak 的 sum waveform（延迟加载波形层）"""
        if not self._waveform_layer_loaded:
            self._load_waveform_layer()

        # 检查缓存
        if peak_id in self._waveform_cache:
            cached = self._waveform_cache[peak_id]
            if copy:
                return {**cached, "waveform": cached["waveform"].copy()}
            return cached

        assert self._peak_id_to_wf_idx is not None
        idx = self._peak_id_to_wf_idx.get(peak_id)
        if idx is None:
            return None

        assert self._peaklet_waveforms is not None
        assert self._peaklet_waveform_pool is not None
        wf = self._peaklet_waveforms[idx]
        wave_offset = int(wf["wave_offset"])
        wave_length = int(wf["wave_length"])

        waveform = self._peaklet_waveform_pool[wave_offset : wave_offset + wave_length]

        time_start_ns, dt_ns, time_rel_ns = self._normalize_waveform_time(wf)

        result = {
            "peak_id": peak_id,
            "waveform": waveform.copy() if copy else waveform,
            "time_start_ns": time_start_ns,
            "time_rel_ns": time_rel_ns,
            "dt_ns": dt_ns,
        }

        if not copy:
            self._waveform_cache[peak_id] = result

        return result

    def pair_waveforms(
        self,
        pair_or_id: int | np.void,
        copy: bool = False,
        missing: str = "raise",
    ) -> tuple[dict, dict] | None:
        """获取配对的 S1 和 S2 波形"""
        pair = self._resolve_pair(pair_or_id, missing=missing)
        if pair is None:
            return None

        s1_peak_id = int(pair["s1_peak_id"])
        s2_peak_id = int(pair["s2_peak_id"])

        s1_wf = self.waveform(s1_peak_id, copy=copy)
        s2_wf = self.waveform(s2_peak_id, copy=copy)

        if s1_wf is None:
            if missing == "raise":
                raise WaveformNotFoundError(f"Missing waveform for s1_peak_id={s1_peak_id}")
            return None

        if s2_wf is None:
            if missing == "raise":
                raise WaveformNotFoundError(f"Missing waveform for s2_peak_id={s2_peak_id}")
            return None

        return s1_wf, s2_wf

    def _resolve_pair(self, pair_or_id: int | np.void, missing: str = "raise") -> np.void | None:
        """解析 pair_id 或 pair row，统一返回 pair row"""
        if isinstance(pair_or_id, int | np.integer):
            pair = self.pair(pair_or_id)
            if pair is None:
                if missing == "raise":
                    raise ValueError(f"Pair {pair_or_id} not found")
                return None
            return pair
        return pair_or_id

    def clear_cache(self) -> None:
        """清理已提取的 waveform 缓存"""
        self._waveform_cache.clear()

    def release_layer(self) -> None:
        """释放整个波形层（包括缓存和原始数据）"""
        self._peaklet_waveforms = None
        self._peaklet_waveform_pool = None
        self._peak_id_to_wf_idx = None
        self._waveform_cache.clear()
        self._waveform_layer_loaded = False

    # ========== 可视化方法 ==========

    def plot(
        self,
        pair_or_id: int | np.void,
        pad_ns: float = 200,
        show_info: bool = True,
        ax: Any = None,
    ) -> Any:
        """在统一时间轴上绘制 S1-S2 配对波形"""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("plot() requires matplotlib. Install it with: pip install matplotlib")

        pair = self._resolve_pair(pair_or_id)

        s1_wf = self.waveform(int(pair["s1_peak_id"]), copy=False)
        s2_wf = self.waveform(int(pair["s2_peak_id"]), copy=False)

        if s1_wf is None:
            raise WaveformNotFoundError(f"Missing waveform for s1_peak_id={pair['s1_peak_id']}")
        if s2_wf is None:
            raise WaveformNotFoundError(f"Missing waveform for s2_peak_id={pair['s2_peak_id']}")

        if ax is None:
            fig, ax = plt.subplots(figsize=(14, 4))
        else:
            fig = ax.get_figure()

        event_t0_ns = s1_wf["time_start_ns"]

        s1_time_rel = (s1_wf["time_start_ns"] - event_t0_ns) + s1_wf["time_rel_ns"]
        s2_time_rel = (s2_wf["time_start_ns"] - event_t0_ns) + s2_wf["time_rel_ns"]

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

        ax.axvline(s1_time_rel[0], color="tab:blue", ls="--", alpha=0.4)
        ax.axvline(s2_time_rel[0], color="tab:orange", ls="--", alpha=0.4)

        t_min = min(s1_time_rel[0], s2_time_rel[0]) - pad_ns
        t_max = max(s1_time_rel[-1], s2_time_rel[-1]) + pad_ns
        ax.set_xlim(t_min, t_max)

        ax.set_xlabel("Time from S1 start (ns)")
        ax.set_ylabel("Amplitude (summed signal)")

        if show_info:
            pair_id = int(pair["pair_id"])
            s1_peak_id = int(pair["s1_peak_id"])
            s2_peak_id = int(pair["s2_peak_id"])
            drift_time_us = float(pair["drift_time_ns"]) / 1000.0
            s1_area = float(pair["s1_area"])
            s2_area = float(pair["s2_area"])
            log10_s2_s1 = float(pair["log10_s2_s1"])

            names = pair.dtype.names
            score_total = float(pair["score_total"]) if "score_total" in names else None
            rank_for_s1 = int(pair["rank_for_s1"]) if "rank_for_s1" in names else None
            rank_for_s2 = int(pair["rank_for_s2"]) if "rank_for_s2" in names else None
            selected = bool(pair["selected"]) if "selected" in names else None

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

    def positions(self) -> np.ndarray:
        """获取位置重建数据"""
        try:
            positions = self.context.get_data(self.run_id, "position_reconstruction")
        except (KeyError, FileNotFoundError):
            from waveform_analysis.core.plugins.builtin.cpu.position_reconstruction import (
                POSITION_RECONSTRUCTION_DTYPE,
            )

            return np.zeros(0, dtype=POSITION_RECONSTRUCTION_DTYPE)

        if self.selected_only and len(self.pairs) > 0:
            pair_ids = self.pairs["pair_id"]
            mask = np.isin(positions["pair_id"], pair_ids)
            positions = positions[mask]

        return positions
