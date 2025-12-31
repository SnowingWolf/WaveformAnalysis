import functools
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.utils.daq.daq import adapt_daq_run
from waveform_analysis.utils.data_processing.loader import get_raw_files, get_waveforms
from waveform_analysis.utils.data_processing.processor import (
    WaveformStruct,
    build_waveform_df,
    find_hits,
    group_multi_channel_hits,
)

from .context import Context
from .mixins import WATCH_SIG_KEY, CacheMixin, PluginMixin, StepMixin, chainable_step
from .plugins import Plugin
from .standard_plugins import HitFinderPlugin, RawFilesPlugin, StWaveformsPlugin, WaveformsPlugin


class WaveformDataset(Context, StepMixin):
    """
    统一的波形数据集容器，封装整个数据处理流程。
    现在基于 Context 构建，利用插件化架构。
    """

    def __init__(
        self,
        char: str = "50V_OV_circulation_20thr",
        n_channels: int = 2,
        start_channel_slice: int = 6,
        data_root: str = "DAQ",
        load_waveforms: bool = True,
        use_daq_scan: bool = False,
        daq_root: Optional[str] = None,
        daq_report: Optional[str] = None,
        show_progress: bool = True,
    ):
        # 初始化 Context (包含 CacheMixin 和 PluginMixin)
        Context.__init__(
            self,
            storage_dir="./cache",
            config={
                "n_channels": n_channels,
                "start_channel_slice": start_channel_slice,
                "data_root": data_root,
                "show_progress": show_progress,
                "load_waveforms": load_waveforms,
            },
        )
        StepMixin.__init__(self)

        self.char = char
        self.n_channels = n_channels
        self.start_channel_slice = start_channel_slice
        self.data_root = data_root
        self.load_waveforms = load_waveforms
        self.show_progress = show_progress

        # 注册默认插件 (使用显式 PluginMixin.register_plugin 以避免 autoreload 导致的 AttributeError)
        from waveform_analysis.core.mixins import PluginMixin as _PluginMixin

        _PluginMixin.register_plugin(self, RawFilesPlugin())
        _PluginMixin.register_plugin(self, WaveformsPlugin())
        _PluginMixin.register_plugin(self, StWaveformsPlugin())
        _PluginMixin.register_plugin(self, HitFinderPlugin())

        # DAQ 集成选项
        self.use_daq_scan = use_daq_scan
        self.daq_root = daq_root or data_root
        self.daq_report = daq_report

        # 多 Run 状态存储 (按 run_id 隔离)
        self._daq_runs: Dict[str, Any] = {}
        self._daq_infos: Dict[str, Any] = {}
        self._timestamp_indices: Dict[str, List[Dict[int, int]]] = {}
        self._run_features: Dict[str, Dict[str, List[np.ndarray]]] = {}

        # 可扩展：特征注册 (全局)
        self.feature_fns: Dict[str, Tuple[Callable[..., List[np.ndarray]], Dict[str, Any]]] = {}

        # 参数缓存 (全局或默认)
        self.peaks_range: Tuple[int, int] = (40, 90)
        self.charge_range: Tuple[int, int] = (60, 400)
        self.time_window_ns: float = 100

        self._validate_data_dir()

    @property
    def data_dir(self):
        return os.path.join(self.data_root, self.char)

    # -------- 兼容性属性 (指向当前 active run: self.char) --------
    @property
    def daq_run(self):
        return self._daq_runs.get(self.char)

    @daq_run.setter
    def daq_run(self, value):
        self._daq_runs[self.char] = value

    @property
    def daq_info(self):
        return self._daq_infos.get(self.char)

    @daq_info.setter
    def daq_info(self, value):
        self._daq_infos[self.char] = value

    @property
    def _timestamp_index(self):
        return self._timestamp_indices.get(self.char, [])

    @_timestamp_index.setter
    def _timestamp_index(self, value):
        self._timestamp_indices[self.char] = value

    @property
    def features(self):
        if self.char not in self._run_features:
            self._run_features[self.char] = {}
        return self._run_features[self.char]

    @features.setter
    def features(self, value):
        self._run_features[self.char] = value

    # -------- 数据属性 (兼容旧代码，映射到 Context._results) --------
    @property
    def raw_files(self) -> List[List[str]]:
        return self._results.get((self.char, "raw_files"), [])

    @raw_files.setter
    def raw_files(self, value):
        self._set_data(self.char, "raw_files", value)

    @property
    def waveforms(self) -> List[np.ndarray]:
        return self._results.get((self.char, "waveforms"), [])

    @waveforms.setter
    def waveforms(self, value):
        self._set_data(self.char, "waveforms", value)

    @property
    def st_waveforms(self) -> List[np.ndarray]:
        return self._results.get((self.char, "st_waveforms"), [])

    @st_waveforms.setter
    def st_waveforms(self, value):
        self._set_data(self.char, "st_waveforms", value)

    @property
    def event_len(self) -> Optional[np.ndarray]:
        return self._results.get((self.char, "event_len"))

    @event_len.setter
    def event_len(self, value):
        self._set_data(self.char, "event_len", value)

    @property
    def peaks(self) -> List[np.ndarray]:
        return self._results.get((self.char, "peaks"), [])

    @peaks.setter
    def peaks(self, value):
        self._set_data(self.char, "peaks", value)

    @property
    def peaks_max_min(self) -> List[np.ndarray]:
        return self._results.get((self.char, "peaks_max_min"), [])

    @peaks_max_min.setter
    def peaks_max_min(self, value):
        self._set_data(self.char, "peaks_max_min", value)

    @property
    def peaks_baseline(self) -> List[np.ndarray]:
        return self._results.get((self.char, "peaks_baseline"), [])

    @peaks_baseline.setter
    def peaks_baseline(self, value):
        self._set_data(self.char, "peaks_baseline", value)

    @property
    def charges(self) -> List[np.ndarray]:
        return self._results.get((self.char, "charges"), [])

    @charges.setter
    def charges(self, value):
        self._set_data(self.char, "charges", value)

    @property
    def hits(self) -> List[np.ndarray]:
        return self._results.get((self.char, "hits"), [])

    @hits.setter
    def hits(self, value):
        self._set_data(self.char, "hits", value)

    @property
    def df(self) -> Optional[pd.DataFrame]:
        return self._results.get((self.char, "df"))

    @df.setter
    def df(self, value):
        self._set_data(self.char, "df", value)

    @property
    def df_events(self) -> Optional[pd.DataFrame]:
        return self._results.get((self.char, "df_events"))

    @df_events.setter
    def df_events(self, value):
        self._set_data(self.char, "df_events", value)

    @property
    def df_paired(self) -> Optional[pd.DataFrame]:
        return self._results.get((self.char, "df_paired"))

    @df_paired.setter
    def df_paired(self, value):
        self._set_data(self.char, "df_paired", value)

    def _ensure_dataframe_for_run(self, run_id: Optional[str]) -> None:
        run_id = run_id or self.char
        if self._get_data_from_memory(run_id, "df") is not None:
            return
        self.load_raw_data(run_id=run_id, verbose=False)
        self.extract_waveforms(run_id=run_id, verbose=False)
        self.structure_waveforms(run_id=run_id, verbose=False)
        self.build_waveform_features(run_id=run_id, verbose=False)
        self.build_dataframe(run_id=run_id, verbose=False)

    def _ensure_grouped_events_for_run(self, run_id: Optional[str], time_window_ns: Optional[float] = None) -> None:
        run_id = run_id or self.char
        if self._get_data_from_memory(run_id, "df_events") is not None:
            return
        self._ensure_dataframe_for_run(run_id)
        self.group_events(run_id=run_id, time_window_ns=time_window_ns, verbose=False)

    def _ensure_paired_events_for_run(self, run_id: Optional[str]) -> None:
        run_id = run_id or self.char
        if self._get_data_from_memory(run_id, "df_paired") is not None:
            return
        self._ensure_grouped_events_for_run(run_id)
        self.pair_events(run_id=run_id, verbose=False)

    # -------- 内部工具 --------

    def _build_timestamp_index(self, run_id: Optional[str] = None):
        """为每个通道构建 timestamp 到行号的映射，加速波形查找。"""
        run_id = run_id or self.char
        st_waveforms = self.get_data(run_id, "st_waveforms") or []

        index = []
        for ch_arr in st_waveforms:
            if len(ch_arr) == 0:
                index.append({})
                continue
            ts = ch_arr["timestamp"].astype(np.int64)
            index.append({int(t): int(i) for i, t in enumerate(ts)})

        self._timestamp_indices[run_id] = index

    def get_data(self, run_id: str, data_name: str, **kwargs) -> Any:
        builder_map = {
            "df": self._ensure_dataframe_for_run,
            "df_events": lambda rid: self._ensure_grouped_events_for_run(rid, time_window_ns=self.time_window_ns),
            "df_paired": self._ensure_paired_events_for_run,
        }

        builder = builder_map.get(data_name)
        if builder:
            builder(run_id)
            val = self._get_data_from_memory(run_id, data_name)
            if val is not None:
                return val

        return super().get_data(run_id, data_name, **kwargs)

    def _ensure_timestamp_index(self, run_id: Optional[str] = None):
        run_id = run_id or self.char
        if run_id not in self._timestamp_indices and self.get_data(run_id, "st_waveforms"):
            self._build_timestamp_index(run_id)

    # -------- 链式步骤装饰器由 StepMixin 提供 --------
    # 移除原有的 _load_persist_data, _save_persist_data, chainable_step 等实现
    # 它们现在在 mixins.py 中定义
    def _get_current_signature(self) -> str:
        """获取当前数据集状态的全局签名（基于 char, n_channels 等）。"""
        import hashlib

        hasher = hashlib.sha1()
        hasher.update(self.char.encode())
        hasher.update(str(self.n_channels).encode())
        hasher.update(str(self.start_channel_slice).encode())
        return hasher.hexdigest()[:8]

    # -------- DAQ 集成方法 --------
    def check_daq_status(self, run_id: Optional[str] = None):
        """尝试使用 DAQAnalyzer（或 JSON 报告）获取当前运行的元信息。

        返回: dict 或 None（若没有找到）
        """
        run_id = run_id or self.char
        # 1) 若指定了 JSON 报告路径，优先使用
        if self.daq_report:
            return self._load_daq_report(self.daq_report, run_id=run_id)

        # 2) 否则使用 DAQAnalyzer 进行扫描（懒导入以避免额外依赖启动开销）
        try:
            from waveform_analysis.utils.daq.daq import DAQAnalyzer

            analyzer = DAQAnalyzer(self.daq_root)
            analyzer.scan_all_runs()
            run = analyzer.get_run(run_id)
            if run is None:
                # 未在扫描结果中找到
                self._daq_runs[run_id] = None
                self._daq_infos[run_id] = None
                return None

            # 保存 DAQRun 对象以便后续使用
            self._daq_runs[run_id] = run
            info = {
                "run_name": run.run_name,
                "path": run.run_path,
                "channels": sorted(run.channels),
            }
            # 也返回 JSON 风格的 channel_details
            channel_details = {}
            for ch in sorted(run.channel_files.keys()):
                files = run.channel_files[ch]
                channel_details[str(ch)] = {
                    "file_count": len(files),
                    "files": [
                        {"filename": f["filename"], "index": f.get("index", 0)}
                        for f in sorted(files, key=lambda x: x.get("index", 0))
                    ],
                }
            info["channel_details"] = channel_details
            self._daq_infos[run_id] = info
            return info
        except Exception:
            # 解析失败则清空状态并返回 None
            if run_id == self.char:
                self.daq_run = None
                self.daq_info = None
            return None

    def _load_daq_report(self, report_path: str, run_id: Optional[str] = None):
        """从 JSON 报告加载运行信息（report_path 可以是文件路径或已经加载的 dict）。"""
        run_id = run_id or self.char
        if isinstance(report_path, dict):
            report = report_path
        else:
            if not os.path.exists(report_path):
                return None
            try:
                import json

                report = json.loads(open(report_path, "r", encoding="utf-8").read())
            except Exception:
                return None

        # 从报告中查找匹配的 run
        for r in report.get("runs", []):
            if r.get("run_name") == run_id:
                self._daq_infos[run_id] = r
                self._daq_runs[run_id] = None
                return r
        return None

    # -------- 扩展：特征注册/计算/落盘到 df --------
    def register_feature(self, name: str, fn: Callable[..., List[np.ndarray]], **params) -> "WaveformDataset":
        """
        注册一个特征计算函数。

        约定：fn(self, st_waveforms, event_len, **params) -> List[np.ndarray]
        返回的 List 长度等于通道数，每个元素为该通道的特征数组（按事件顺序）。
        """
        self.feature_fns[name] = (fn, params)
        return self

    @chainable_step
    def compute_registered_features(self, run_id: Optional[str] = None, verbose: bool = True) -> "WaveformDataset":
        run_id = run_id or self.char
        st_waveforms = self.get_data(run_id, "st_waveforms")
        event_len = self.get_data(run_id, "event_len")

        if not st_waveforms or event_len is None:
            raise RuntimeError(f"[{run_id}] 需要先调用 structure_waveforms()")

        # 初始化该 run 的特征字典
        self._run_features[run_id] = {}

        items = self.feature_fns.items()
        if self.show_progress:
            try:
                from tqdm import tqdm

                items = tqdm(items, desc=f"[{run_id}] Computing registered features", leave=False)
            except ImportError:
                pass

        for name, (fn, params) in items:
            vals = fn(self, st_waveforms, event_len, **params)
            self._run_features[run_id][name] = vals
            if verbose:
                print(f"[{run_id}] [features] {name}: {[len(v) for v in vals]} (per-channel)")
        return self

    # -------- 链式步骤相关工具 --------
    def list_chainable_steps(self) -> List[str]:
        """Return a list of method names on this class that are likely chainable steps.

        Heuristic: public callables on the class that have been wrapped (functools.wraps)
        by the `chainable_step` decorator will expose a `__wrapped__` attribute.
        """
        steps: List[str] = []
        for name in dir(self.__class__):
            if name.startswith("_"):
                continue
            try:
                attr = getattr(self.__class__, name)
            except Exception:
                continue
            if callable(attr) and hasattr(attr, "__wrapped__"):
                steps.append(name)
        return sorted(steps)

    def get_configured_cache_steps(self) -> Dict[str, Dict[str, object]]:
        """Return the current step cache configuration dictionary (step_name -> config).

        Useful to inspect which steps have caching/persistence enabled.
        """
        return dict(self._cache_config)

    def _concat_by_channel(self, values: List[np.ndarray]) -> np.ndarray:
        """
        将按通道的特征数组按 build_waveform_df 的顺序进行连接，
        保证与 df 的行顺序一致。
        """
        parts: List[np.ndarray] = []
        if self.event_len is None:
            raise RuntimeError("事件长度未定义，请确认已成功结构化波形")
        for ch in range(self.n_channels):
            n = int(self.event_len[ch])
            arr = np.asarray(values[ch])[:n]
            parts.append(arr)
        return np.concatenate(parts) if parts else np.array([], dtype=float)

    def add_features_to_dataframe(
        self, run_id: Optional[str] = None, names: Optional[List[str]] = None, verbose: bool = True
    ) -> "WaveformDataset":
        run_id = run_id or self.char
        df = self.get_data(run_id, "df")
        features = self._run_features.get(run_id, {})

        if df is None:
            raise RuntimeError(f"[{run_id}] 需要先调用 build_dataframe()")
        if not features:
            if verbose:
                print(f"[{run_id}] [features] 没有可用的特征，可先调用 compute_registered_features()")
            return self

        target_names = names or list(features.keys())
        for name in target_names:
            vals = features.get(name)
            if vals is None:
                continue
            col = self._concat_by_channel(vals)
            if len(col) != len(df):
                # 保护：长度不一致则跳过，避免污染 df
                if verbose:
                    print(f"[{run_id}] [features] 跳过列 {name}（长度 {len(col)} != df 行数 {len(df)}）")
                continue
            df[name] = col
            if verbose:
                print(f"[{run_id}] [features] 已添加列: {name}")
        return self

    def _validate_data_dir(self):
        """验证数据目录是否存在。若启用了 DAQ 扫描，可在目录缺失时尝试从 DAQ 扫描获取运行信息。"""
        # 如果启用了 DAQ 扫描，无论目录是否存在都尝试获取 DAQ 信息
        if self.use_daq_scan:
            try:
                self.check_daq_status()
            except Exception as e:
                print(f"[warning] DAQ status check failed: {e}")

        if not os.path.exists(self.data_dir):
            if not self.use_daq_scan:
                raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")

            # 如果目录不存在且 DAQ 扫描也没找到，则报错
            if self.daq_run is None:
                raise FileNotFoundError(f"数据目录 {self.data_dir} 不存在，且 DAQ 扫描未发现运行 {self.char}")

    @chainable_step
    def load_raw_data(self, run_id: Optional[str] = None, verbose: bool = True) -> "WaveformDataset":
        """
        加载原始 CSV 文件。现在通过插件系统实现。
        """
        run_id = run_id or self.char
        raw_files = self.get_data(run_id, "raw_files")

        if verbose:
            print(f"[{run_id}] 加载 {len(raw_files)} 个通道的原始文件")
            for ch, fs in enumerate(raw_files):
                if fs:
                    print(f"  CH{ch}: {len(fs)} 个文件")

        return self

    @chainable_step
    def extract_waveforms(self, run_id: Optional[str] = None, verbose: bool = True) -> "WaveformDataset":
        """
        从原始文件中提取波形数据。现在通过插件系统实现。
        """
        if not self.load_waveforms:
            if verbose:
                print("  跳过波形提取（load_waveforms=False）")
            return self

        run_id = run_id or self.char
        waveforms = self.get_data(run_id, "waveforms")

        if verbose:
            for ch, wf in enumerate(waveforms):
                if wf.size == 0:
                    print(f"  CH{self.start_channel_slice + ch}: 空数组")
                else:
                    print(f"  CH{self.start_channel_slice + ch}: {wf.shape}")

        return self

    @chainable_step
    def structure_waveforms(self, run_id: Optional[str] = None, verbose: bool = True) -> "WaveformDataset":
        """
        将波形数据转换为结构化 numpy 数组。现在通过插件系统实现。
        """
        if not self.load_waveforms:
            if verbose:
                print("  跳过波形结构化（load_waveforms=False）")
            return self

        run_id = run_id or self.char
        st_waveforms = self.get_data(run_id, "st_waveforms")
        event_len = self.get_data(run_id, "event_len")

        # 预构建 timestamp -> index 加速表
        self._build_timestamp_index(run_id)

        if verbose:
            print(f"[{run_id}] 结构化波形完成，事件长度: {event_len}")
            for i in range(len(st_waveforms)):
                if len(st_waveforms[i]) > 0:
                    print(f"  通道 {i}: 字段 {list(st_waveforms[i].dtype.names)}")

        return self

    @chainable_step
    def build_waveform_features(
        self,
        run_id: Optional[str] = None,
        peaks_range: Optional[Tuple[int, int]] = None,
        charge_range: Optional[Tuple[int, int]] = None,
        verbose: bool = True,
    ) -> "WaveformDataset":
        """
        计算波形特征（peaks 和 charges）。

        参数:
            run_id: 运行 ID
            peaks_range: peak 窗口 (start, end)
            charge_range: charge 窗口 (start, end)
            verbose: 是否打印日志

        返回: self（便于链式调用）
        """
        run_id = run_id or self.char
        st_waveforms = self.get_data(run_id, "st_waveforms")
        event_len = self.get_data(run_id, "event_len")

        if not st_waveforms:
            raise RuntimeError(f"[{run_id}] 需要先调用 structure_waveforms()")
        if event_len is None:
            raise RuntimeError(f"[{run_id}] 事件长度未定义，请确认已成功结构化波形")

        if peaks_range is not None:
            self.peaks_range = peaks_range
        if charge_range is not None:
            self.charge_range = charge_range

        start_p, end_p = self.peaks_range
        start_c, end_c = self.charge_range

        # Optional progress bar for feature calculation
        if self.show_progress:
            try:
                from tqdm import tqdm

                pbar = tqdm(range(len(st_waveforms)), desc=f"[{run_id}] Calculating features", leave=False)
            except ImportError:
                pbar = range(len(st_waveforms))
        else:
            pbar = range(len(st_waveforms))

        peaks_max_min = []
        peaks_baseline = []
        charges = []

        for i in pbar:
            st_ch = st_waveforms[i]
            n = event_len[i]

            if len(st_ch) == 0:
                peaks_max_min.append(np.array([]))
                peaks_baseline.append(np.array([]))
                charges.append(np.array([]))
                continue

            # 尝试向量化计算以提升性能
            try:
                # st_ch["wave"] 是 object 数组，尝试将其堆叠为 2D 数组
                waves_2d = np.stack(st_ch["wave"][:n])

                # 提取窗口数据
                wave_p = waves_2d[:, start_p:end_p]
                wave_c = waves_2d[:, start_c:end_c]
                baselines = st_ch["baseline"][:n]

                # 向量化计算特征
                p_mm = np.max(wave_p, axis=1) - np.min(wave_p, axis=1)
                peaks_max_min.append(p_mm)
                peaks_baseline.append(baselines)

                # Charge 计算 (sum - baseline * window_size)
                c_sum = np.sum(wave_c, axis=1)
                charges.append(c_sum - baselines * (end_c - start_c))
            except Exception as e:
                if verbose:
                    print(f"  [warning] 通道 {i} 特征计算失败: {e}")
                peaks_max_min.append(np.array([]))
                peaks_baseline.append(np.array([]))
                charges.append(np.array([]))

        # 保存结果到 Context
        self._set_data(run_id, "peaks_max_min", peaks_max_min)
        self._set_data(run_id, "peaks_baseline", peaks_baseline)
        self._set_data(run_id, "charges", charges)

        if verbose:
            print(f"[{run_id}] 特征计算完成: peaks_max_min, charges")

        return self

    @chainable_step
    def find_hits(
        self,
        run_id: Optional[str] = None,
        threshold: float = 10.0,
        left_extension: int = 2,
        right_extension: int = 2,
        verbose: bool = True,
    ) -> "WaveformDataset":
        """
        使用向量化寻峰算法（Hit-finding）查找波形中的脉冲。现在通过插件系统实现。
        """
        run_id = run_id or self.char
        hits = self.get_data(
            run_id,
            "hits",
            threshold=threshold,
            left_extension=left_extension,
            right_extension=right_extension,
        )

        if verbose:
            for i, h in enumerate(hits):
                print(f"[{run_id}] 通道 {i}: 找到 {len(h)} 个 hits")

        return self

    @chainable_step
    def group_hits(self, run_id: Optional[str] = None, verbose: bool = True) -> "WaveformDataset":
        """
        将多通道 hits 按事件分组。
        """
        run_id = run_id or self.char
        hits = self.get_data(run_id, "hits")

        if not hits:
            raise RuntimeError(f"[{run_id}] 需要先调用 find_hits()")

        # 合并所有通道的 hits
        all_hits = np.concatenate([h for h in hits if len(h) > 0])
        if len(all_hits) == 0:
            self._set_data(run_id, "df", pd.DataFrame())
            return self

        # 按 event_index 分组
        df = pd.DataFrame(all_hits)
        self._set_data(run_id, "df", df)

        if verbose:
            print(f"[{run_id}] Hits 分组完成，共 {len(df)} 个 hits")

        return self

    @chainable_step
    def apply_plugin(self, run_id: Optional[str] = None, data_name: str = "", **kwargs) -> "WaveformDataset":
        """
        Run a registered plugin and store its result.
        """
        run_id = run_id or self.char
        self.get_data(run_id, data_name, **kwargs)
        return self

    @chainable_step
    def build_dataframe(self, run_id: Optional[str] = None, verbose: bool = True) -> "WaveformDataset":
        """
        构建波形 DataFrame（单通道事件列表）。
        """
        run_id = run_id or self.char
        peaks = self.get_data(run_id, "peaks_max_min")
        charges = self.get_data(run_id, "charges")
        st_waveforms = self.get_data(run_id, "st_waveforms")
        event_len = self.get_data(run_id, "event_len")
        peaks_baseline = self.get_data(run_id, "peaks_baseline")

        if not peaks or not charges:
            raise RuntimeError(f"[{run_id}] 需要先调用 build_waveform_features()")

        df = build_waveform_df(
            st_waveforms,
            peaks,
            charges,
            event_len,
            n_channels=self.n_channels,
            peak_max_min=peaks,
            peak_baseline=peaks_baseline,
        )

        # 将注册特征（如有）落盘到 df
        if self._run_features.get(run_id) or self.feature_fns:
            if not self._run_features.get(run_id):
                self.compute_registered_features(run_id=run_id, verbose=False)
            self.add_features_to_dataframe(run_id=run_id, verbose=False)

        df.sort_values("timestamp", inplace=True)
        self._set_data(run_id, "df", df)

        if verbose:
            print(f"[{run_id}] 构建 DataFrame 完成，事件总数: {len(df)}")

        return self

    @chainable_step
    def group_events(
        self, run_id: Optional[str] = None, time_window_ns: Optional[float] = None, verbose: bool = True
    ) -> "WaveformDataset":
        """
        按时间窗口聚类多通道事件。
        """
        run_id = run_id or self.char
        df = self.get_data(run_id, "df")

        if df is None:
            raise RuntimeError(f"[{run_id}] 需要先调用 build_dataframe()")

        if time_window_ns is not None:
            self.time_window_ns = time_window_ns

        df_events = group_multi_channel_hits(df, self.time_window_ns, show_progress=self.show_progress)
        self._set_data(run_id, "df_events", df_events)

        if verbose:
            print(f"[{run_id}] 聚类完成，事件组数: {len(df_events)}")
            hit_counts = df_events["n_hits"].value_counts().sort_index()
            print(f"  事件类型分布:\n{hit_counts}")

        return self

    @chainable_step
    def pair_events(self, run_id: Optional[str] = None, verbose: bool = True) -> "WaveformDataset":
        """
        筛选成对的 N 通道事件。
        """
        run_id = run_id or self.char
        df_events = self.get_data(run_id, "df_events")

        if df_events is None:
            raise RuntimeError(f"[{run_id}] 需要先调用 group_events()")

        # 优化：使用位掩码进行快速筛选
        expected_mask = (1 << self.n_channels) - 1

        if "channel_mask" not in df_events.columns:
            from waveform_analysis.utils.data_processing.processor import encode_channels_binary

            df_events["channel_mask"] = df_events["channels"].apply(encode_channels_binary)

        df_paired = df_events[
            (df_events["n_hits"] == self.n_channels) & (df_events["channel_mask"] == expected_mask)
        ].copy()

        if len(df_paired) == 0:
            self._set_data(run_id, "df_paired", df_paired)
            if verbose:
                print(f"[{run_id}] 警告: 没有找到符合条件的配对事件")
            return self

        # 计算时间差（单位: ns）
        ts_stacked = np.stack(df_paired["timestamps"].values)
        df_paired["delta_t"] = (ts_stacked[:, -1] - ts_stacked[:, 0]) / 1000.0

        # 提取各通道的 charges 和 peaks
        # 优化：向量化提取
        charges_stacked = np.stack(df_paired["charges"].values)
        peaks_stacked = np.stack(df_paired["peaks"].values)

        for i in range(self.n_channels):
            df_paired[f"charge_ch{self.start_channel_slice + i}"] = charges_stacked[:, i]
            df_paired[f"peak_ch{self.start_channel_slice + i}"] = peaks_stacked[:, i]

        self._set_data(run_id, "df_paired", df_paired)

        if verbose:
            print(f"[{run_id}] 配对完成，成功配对的事件数: {len(df_paired)}")

        return self

    # 可插拔配对策略：允许自定义过滤规则
    def pair_events_with(
        self, strategy: Callable[[pd.DataFrame, int], pd.DataFrame], run_id: Optional[str] = None, verbose: bool = True
    ) -> "WaveformDataset":
        """
        使用自定义策略对 df_events 进行配对过滤。

        参数:
            strategy(df_events, n_channels) -> DataFrame  返回配对后的 DataFrame
            run_id: 运行 ID
            verbose: 是否打印日志
        """
        run_id = run_id or self.char
        df_events = self.get_data(run_id, "df_events")

        if df_events is None:
            raise RuntimeError(f"[{run_id}] 需要先调用 group_events()")

        df_paired = strategy(df_events, self.n_channels).copy()

        # 若策略未计算 delta_t，这里进行补充
        if "timestamps" in df_paired.columns and "delta_t" not in df_paired.columns:
            df_paired["delta_t"] = df_paired["timestamps"].apply(lambda x: (x[-1] - x[0]) / 1000.0)

        # 若策略保留了 charges / peaks，则生成派生列
        if "charges" in df_paired.columns:
            for i in range(min(self.n_channels, 8)):
                df_paired[f"charge_ch{self.start_channel_slice + i}"] = df_paired["charges"].apply(
                    lambda x: x[i] if len(x) > i else np.nan
                )
        if "peaks" in df_paired.columns:
            for i in range(min(self.n_channels, 8)):
                df_paired[f"peak_ch{self.start_channel_slice + i}"] = df_paired["peaks"].apply(
                    lambda x: x[i] if len(x) > i else np.nan
                )

        self._set_data(run_id, "df_paired", df_paired)

        if verbose:
            print(f"[{run_id}] 配对完成，成功配对的事件数: {len(df_paired)}")

        return self

    def get_raw_events(self) -> Optional[pd.DataFrame]:
        """获取原始事件 DataFrame（未分组）。"""
        return self.df

    def get_grouped_events(self) -> Optional[pd.DataFrame]:
        """获取分组后的事件 DataFrame。"""
        return self.df_events

    def get_paired_events(self) -> Optional[pd.DataFrame]:
        """获取配对的事件 DataFrame。"""
        return self.df_paired

    def get_waveform_at(
        self, event_idx: int, channel: int = 0, run_id: Optional[str] = None
    ) -> Optional[Tuple[np.ndarray, float]]:
        """
        获取指定事件和通道的原始波形及其 baseline。

        参数:
            event_idx: df_paired 中的事件索引
            channel: 通道索引（相对于 start_channel_slice）
            run_id: 运行 ID (默认为当前 active run)

        返回: (波形数组, baseline) 或 None
        """
        run_id = run_id or self.char
        if not self.load_waveforms:
            print("⚠️  波形数据未加载（load_waveforms=False）")
            return None

        df_paired = self.get_data(run_id, "df_paired")
        if df_paired is None or event_idx >= len(df_paired):
            return None

        event = df_paired.iloc[event_idx]
        ts = event["timestamps"][channel]

        # 使用预构建索引加速查找
        self._ensure_timestamp_index(run_id)
        timestamp_index = self._timestamp_indices.get(run_id, [])
        idx_map = timestamp_index[channel] if channel < len(timestamp_index) else {}
        idx = idx_map.get(int(ts), -1)
        if idx == -1:
            return None

        try:
            st_waveforms = self.get_data(run_id, "st_waveforms")
            wave = st_waveforms[channel][idx]["wave"]
            baseline = st_waveforms[channel][idx]["baseline"]
            return wave, baseline
        except (IndexError, ValueError, KeyError):
            return None

    def save_results(
        self, run_id: Optional[str] = None, output_dir: str = "outputs", verbose: bool = True
    ) -> "WaveformDataset":
        """
        保存处理结果（CSV 和 Parquet 格式）。
        """
        run_id = run_id or self.char
        df_paired = self.get_data(run_id, "df_paired")

        os.makedirs(output_dir, exist_ok=True)

        if df_paired is not None and len(df_paired) > 0:
            csv_path = os.path.join(output_dir, f"{run_id}_paired.csv")
            pq_path = os.path.join(output_dir, f"{run_id}_paired.parquet")

            df_paired.to_csv(csv_path, index=False)
            df_paired.to_parquet(pq_path)

            if verbose:
                print(f"[{run_id}] 已保存: {csv_path}")
                print(f"[{run_id}] 已保存: {pq_path}")
        else:
            if verbose:
                print(f"[{run_id}] 没有配对事件，跳过保存")

        return self

    def summary(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取数据处理摘要信息。
        """
        run_id = run_id or self.char

        # 使用 get_data 获取当前 run 的数据
        raw_files = self.get_data(run_id, "raw_files")
        waveforms = self.get_data(run_id, "waveforms")
        df = self.get_data(run_id, "df")
        df_events = self.get_data(run_id, "df_events")
        df_paired = self.get_data(run_id, "df_paired")

        base = {
            "dataset": run_id,
            "n_channels": self.n_channels,
            "raw_files_count": sum(len(f) for f in raw_files) if raw_files else 0,
            "waveforms_shape": [w.shape if w.size > 0 else "empty" for w in waveforms] if waveforms else [],
            "raw_events": len(df) if df is not None else 0,
            "grouped_events": len(df_events) if df_events is not None else 0,
            "paired_events": len(df_paired) if df_paired is not None else 0,
            "features_config": {
                "peaks_range": self.peaks_range,
                "charge_range": self.charge_range,
                "time_window_ns": self.time_window_ns,
            },
        }

        # DAQ 相关信息（若启用且可用）
        daq_summary: Dict[str, Any] = {"enabled": bool(self.use_daq_scan), "found": False}

        if self.daq_run is not None:
            try:
                self.daq_run.compute_acquisition_times()
            except Exception:
                pass

            # 更稳健地访问 DAQRun 属性，防止缺失导致异常
            daq_summary.update({
                "found": True,
                "run_path": getattr(self.daq_run, "run_path", None),
                "channels": sorted(list(self.daq_run.channels))
                if getattr(self.daq_run, "channels", None) is not None
                else [],
                "channel_count": len(self.daq_run.channels)
                if getattr(self.daq_run, "channels", None) is not None
                else 0,
            })

            chs = {}
            for ch, s in self.daq_run.get_channel_summary().items():
                chs[str(ch)] = {
                    "file_count": s.get("file_count"),
                    "total_size_bytes": s.get("total_size_bytes"),
                    "start_time_ps": s.get("start_time_ps"),
                    "end_time_ps": s.get("end_time_ps"),
                    "duration_s": s.get("duration_s"),
                }
            daq_summary["channels_summary"] = chs

        elif self.daq_info is not None:
            daq_summary.update({
                "found": True,
                "run_path": self.daq_info.get("path"),
                "channels": self.daq_info.get("channels", []),
            })
            chs = {}
            for ch_str, chdata in (self.daq_info.get("channel_details") or {}).items():
                chs[str(ch_str)] = {
                    "file_count": chdata.get("file_count"),
                    "files": [f.get("filename") for f in chdata.get("files", [])],
                }
            daq_summary["channels_summary"] = chs

        base["daq"] = daq_summary
        return base

    @classmethod
    def from_daq_report(
        cls,
        char: str,
        daq_report: str | dict,
        data_root: str = "DAQ",
        load_waveforms: bool = True,
        run_pipeline: bool = True,
        n_channels: int = 2,
        start_channel_slice: int = 6,
        time_window_ns: float | None = None,
    ) -> "WaveformDataset":
        """基于 DAQ JSON 报告或 report dict 创建并可选地运行完整处理流程的便利工厂。

        参数:
            char: 运行名
            daq_report: JSON 文件路径或已加载的 dict
            data_root: DAQ 根目录（仅用于相对路径解析）
            load_waveforms: 是否在管道中加载原始波形
            run_pipeline: 是否运行整个处理流程（加载 -> 提取 -> 结构化 -> 特征 -> df -> 聚类 -> 配对）
            n_channels: 处理通道数
            start_channel_slice: 起始通道索引
            time_window_ns: 可选的时间窗口覆盖默认值

        返回: WaveformDataset 实例
        """
        ds = cls(
            char=char,
            n_channels=n_channels,
            start_channel_slice=start_channel_slice,
            data_root=data_root,
            load_waveforms=load_waveforms,
            use_daq_scan=True,
            daq_root=data_root,
            daq_report=daq_report,
        )

        # 初始化 DAQ 信息并加载 raw_files
        ds.check_daq_status()
        ds.load_raw_data(verbose=False)

        if run_pipeline:
            # 执行典型 pipeline
            ds.extract_waveforms(verbose=False)
            ds.structure_waveforms(verbose=False)
            ds.build_waveform_features(verbose=False)
            ds.build_dataframe(verbose=False)
            if time_window_ns is not None:
                ds.group_events(time_window_ns=time_window_ns, verbose=False)
            else:
                ds.group_events(verbose=False)
            ds.pair_events(verbose=False)

        return ds

    def __repr__(self) -> str:
        """数据集对象的字符串表示。"""
        return (
            f"WaveformDataset(char='{self.char}', n_channels={self.n_channels}, "
            f"raw_events={len(self.df) if self.df is not None else 0}, "
            f"paired_events={len(self.df_paired) if self.df_paired is not None else 0})"
        )
