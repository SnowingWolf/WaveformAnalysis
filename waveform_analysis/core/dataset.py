import functools
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .loader import get_raw_files, get_waveforms
from .processor import WaveformStruct, build_waveform_df, group_multi_channel_hits


class WaveformDataset:
    """
    统一的波形数据集容器，封装整个数据处理流程。
    支持链式调用，简化数据加载、预处理和分析。
    
    使用示例：
        dataset = WaveformDataset(char="50V_OV_circulation_20thr", n_channels=2)
        dataset.load_raw_data().extract_waveforms().structure_waveforms()\\
               .build_waveform_features().build_dataframe().group_events()\\
               .pair_events().save_results()
        
        df_paired = dataset.get_paired_events()
        summary = dataset.summary()
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
    ):
        """
        初始化数据集。

        参数:
            char: 数据集标识符
            n_channels: 要处理的通道数
            start_channel_slice: 开始通道索引（通常为 6 表示 CH6/CH7）
            data_root: 数据根目录
            load_waveforms: 是否加载原始波形数据（默认 True）
                           - True: 加载所有波形，支持 get_waveform_at()
                           - False: 仅加载特征（峰值、电荷等），节省内存 (70-80% 内存节省)
        """
        self.char = char
        self.n_channels = n_channels
        self.start_channel_slice = start_channel_slice
        self.data_root = data_root
        self.data_dir = os.path.join(data_root, char)
        self.load_waveforms = load_waveforms

        # DAQ 集成选项
        self.use_daq_scan = use_daq_scan
        self.daq_root = daq_root or data_root
        self.daq_report = daq_report
        self.daq_run = None  # 若由 DAQAnalyzer 扫描得到的 DAQRun 对象
        self.daq_info = None  # 若由 JSON 报告加载的 dict

        # 数据容器
        self.raw_files: List[List[str]] = []
        self.waveforms: List[np.ndarray] = []
        self.st_waveforms: List[np.ndarray] = []
        self.pair_len: Optional[np.ndarray] = None

        # 特征和结果
        self.peaks: List[np.ndarray] = []
        self.charges: List[np.ndarray] = []
        self.df: Optional[pd.DataFrame] = None
        self.df_events: Optional[pd.DataFrame] = None
        self.df_paired: Optional[pd.DataFrame] = None

        # 缓存：timestamp -> index（减少 get_waveform_at 中的 np.where 开销）
        self._timestamp_index: List[Dict[int, int]] = []

        # 可扩展：特征注册与结果缓存
        self.feature_fns: Dict[str, Tuple[Callable[..., List[np.ndarray]], Dict[str, Any]]] = {}
        self.features: Dict[str, List[np.ndarray]] = {}

        # 参数缓存
        self.peaks_range: Tuple[int, int] = (40, 90)
        self.charge_range: Tuple[int, int] = (60, 400)
        self.time_window_ns: float = 100

        self._validate_data_dir()

        # 链式步骤错误/状态跟踪
        self._step_errors: Dict[str, str] = {}
        self._step_status: Dict[str, str] = {}
        self._last_failed_step: Optional[str] = None
        self.raise_on_error: bool = False

        # 步骤缓存（内存 + 可选磁盘持久化配置）
        # _cache: { step_name: {attr_name: value, ...} }
        self._cache: Dict[str, Dict[str, object]] = {}
        # _cache_config: { step_name: {enabled: bool, attrs: [str], persist_path: Optional[str]} }
        self._cache_config: Dict[str, Dict[str, object]] = {}

    # -------- 内部工具 --------

    def _build_timestamp_index(self):
        """为每个通道构建 timestamp 到行号的映射，加速波形查找。"""
        self._timestamp_index = []
        for ch_arr in self.st_waveforms:
            if len(ch_arr) == 0:
                self._timestamp_index.append({})
                continue
            ts = ch_arr["timestamp"].astype(np.int64)
            self._timestamp_index.append({int(t): int(i) for i, t in enumerate(ts)})

    # -------- 链式步骤装饰器（错误容忍） --------
    def _record_step_success(self, name: str) -> None:
        self._step_status[name] = "success"

    def _record_step_failure(self, name: str, exc: Exception) -> None:
        self._step_status[name] = "failed"
        self._step_errors[name] = str(exc)
        self._last_failed_step = name

    @staticmethod
    def chainable_step(fn: Callable):
        """装饰器：将步骤错误捕获并记录，支持可选的步骤级缓存配置（内存/磁盘）。

        说明：使用 `ds.set_step_cache(step_name, enabled=True, attrs=[...], persist_path=...)`
        可以为某一步启用缓存。
        """
        """装饰器：将步骤错误捕获并记录，默认不抛出异常以保证链式调用不中断。

        使用：在 dataset 的方法上加上 @WaveformDataset.chainable_step
        """

        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            name = fn.__name__
            # 先检查缓存配置（若启用且缓存存在则直接加载并返回 self）
            cfg = getattr(self, "_cache_config", {}).get(name, {})
            if cfg.get("enabled"):
                # 磁盘持久化优先检查
                persist = cfg.get("persist_path")
                loaded = False
                if persist:
                    try:
                        import pickle

                        if os.path.exists(persist):
                            with open(persist, "rb") as f:
                                data = pickle.load(f)

                            # If watch_attrs are configured, validate signature
                            watch_attrs = cfg.get("watch_attrs") or []
                            saved_sig = data.get("__watch_sig__")
                            if watch_attrs and saved_sig is not None:
                                try:
                                    current_sig = self._compute_watch_signature(watch_attrs)
                                except Exception:
                                    current_sig = None

                                # If signatures mismatch, ignore persisted cache
                                if current_sig != saved_sig:
                                    # treat as cache miss and fallthrough to execute step
                                    loaded = False
                                else:
                                    # restore cached attrs (excluding internal signature)
                                    for k, v in data.items():
                                        if k == "__watch_sig__":
                                            continue
                                        setattr(self, k, v)
                                    self._cache[name] = {k: v for k, v in data.items() if k != "__watch_sig__"}
                                    self._record_step_success(name)
                                    return self
                            else:
                                # No watch_attrs configured or saved signature absent: restore as before
                                for k, v in data.items():
                                    setattr(self, k, v)
                                self._cache[name] = data
                                self._record_step_success(name)
                                return self
                    except Exception:
                        # 忽略磁盘加载错误，继续尝试内存缓存或执行步骤
                        pass

                # 内存缓存检查
                mem = getattr(self, "_cache", {}).get(name)
                if mem is not None:
                    for k, v in mem.items():
                        setattr(self, k, v)
                    self._record_step_success(name)
                    return self

            try:
                res = fn(self, *args, **kwargs)
                # 期望步骤返回 self；如果返回其他类型也处理
                try:
                    # 若配置了缓存，则保存指定属性
                    if cfg.get("enabled"):
                        attrs = cfg.get("attrs") or []
                        cache_data = {}
                        for a in attrs:
                            cache_data[a] = getattr(self, a, None)

                        # If watch_attrs configured, compute signature and include it
                        watch_attrs = cfg.get("watch_attrs") or []
                        if watch_attrs:
                            try:
                                sig = self._compute_watch_signature(watch_attrs)
                                cache_data["__watch_sig__"] = sig
                            except Exception:
                                # ignore signature computation errors
                                pass

                        # 保存到内存
                        self._cache[name] = {k: v for k, v in cache_data.items() if k != "__watch_sig__"}
                        # 持久化到磁盘（如果配置）
                        persist = cfg.get("persist_path")
                        if persist:
                            try:
                                import pickle

                                os.makedirs(os.path.dirname(persist), exist_ok=True)
                                with open(persist, "wb") as f:
                                    pickle.dump(cache_data, f)
                            except Exception:
                                # 忽略磁盘写入错误
                                pass

                    self._record_step_success(name)
                except Exception:
                    pass
                return res
            except Exception as e:
                try:
                    self._record_step_failure(name, e)
                except Exception:
                    pass
                # 可选：根据配置决定是否重新抛出
                if getattr(self, "raise_on_error", False):
                    raise
                # 打印警告并返回 self，保证链式安全
                print(f"[warning] step '{name}' failed: {e}")
                return self

        return wrapper

    def _ensure_timestamp_index(self):
        if not self._timestamp_index:
            self._build_timestamp_index()

    def _compute_watch_signature(self, attrs: List[str]) -> Optional[str]:
        """基于给定属性列表（通常是包含文件路径的属性）计算一个轻量级签名（sha1）。

        支持属性为单路径字符串、列表/嵌套列表、或者 dict（尝试提取可能的路径字段）。
        返回：hex digest 字符串（或 None 如果没有可用文件）
        """
        import hashlib

        files = []

        def _gather(val):
            if val is None:
                return
            if isinstance(val, str):
                files.append(val)
            elif isinstance(val, (list, tuple)):
                for v in val:
                    _gather(v)
            elif isinstance(val, dict):
                # 尝试从 dict 中提取可能的路径字段
                for k, v in val.items():
                    if isinstance(v, str) and (
                        os.path.exists(v) or v.lower().endswith(".csv") or v.startswith("./") or v.startswith("/")
                    ):
                        files.append(v)
                    else:
                        _gather(v)

        for a in attrs:
            try:
                val = getattr(self, a, None)
            except Exception:
                val = None
            _gather(val)

        entries = []
        for fp in sorted(set(files)):
            try:
                if not os.path.exists(fp):
                    # include non-existent path marker
                    entries.append((fp, None, None))
                    continue
                m = os.path.getmtime(fp)
                s = os.path.getsize(fp)
                entries.append((fp, float(m), int(s)))
            except Exception:
                entries.append((fp, None, None))

        if not entries:
            return None

        m = hashlib.sha1()
        for p, mt, sz in entries:
            m.update(str(p).encode("utf-8"))
            m.update(b"|")
            m.update(str(mt).encode("utf-8") if mt is not None else b"None")
            m.update(b"|")
            m.update(str(sz).encode("utf-8") if sz is not None else b"None")
            m.update(b"\n")

        return m.hexdigest()

    # -------- DAQ 集成方法 --------
    def check_daq_status(self):
        """尝试使用 DAQAnalyzer（或 JSON 报告）获取当前运行的元信息。

        返回: dict 或 None（若没有找到）
        """
        # 1) 若指定了 JSON 报告路径，优先使用
        if self.daq_report:
            return self._load_daq_report(self.daq_report)

        # 2) 否则使用 DAQAnalyzer 进行扫描（懒导入以避免额外依赖启动开销）
        try:
            from waveform_analysis.utils.daq import DAQAnalyzer

            analyzer = DAQAnalyzer(self.daq_root)
            analyzer.scan_all_runs()
            run = analyzer.get_run(self.char)
            if run is None:
                # 未在扫描结果中找到
                self.daq_run = None
                self.daq_info = None
                return None

            # 保存 DAQRun 对象以便后续使用
            self.daq_run = run
            self.daq_info = {
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
            self.daq_info["channel_details"] = channel_details
            return self.daq_info
        except Exception:
            # 解析失败则清空状态并返回 None
            self.daq_run = None
            self.daq_info = None
            return None

    def _load_daq_report(self, report_path: str):
        """从 JSON 报告加载运行信息（report_path 可以是文件路径或已经加载的 dict）。"""
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
            if r.get("run_name") == self.char:
                self.daq_info = r
                self.daq_run = None
                return r
        return None

    # -------- 扩展：特征注册/计算/落盘到 df --------
    def register_feature(self, name: str, fn: Callable[..., List[np.ndarray]], **params) -> "WaveformDataset":
        """
        注册一个特征计算函数。

        约定：fn(self, st_waveforms, pair_len, **params) -> List[np.ndarray]
        返回的 List 长度等于通道数，每个元素为该通道的特征数组（按事件顺序）。
        """
        self.feature_fns[name] = (fn, params)
        return self

    @chainable_step
    def compute_registered_features(self, verbose: bool = True) -> "WaveformDataset":
        if not self.st_waveforms or self.pair_len is None:
            raise RuntimeError("需要先调用 structure_waveforms()")
        self.features = {}
        for name, (fn, params) in self.feature_fns.items():
            vals = fn(self, self.st_waveforms, self.pair_len, **params)
            self.features[name] = vals
            if verbose:
                print(f"[features] {name}: {[len(v) for v in vals]} (per-channel)")
        return self

    # -------- 链式步骤相关工具 --------
    def get_step_errors(self) -> Dict[str, str]:
        """返回所有步骤的错误信息字典（步骤名 → 错误文本）。"""
        return dict(self._step_errors)

    def clear_step_errors(self) -> None:
        """清除记录的步骤错误。"""
        self._step_errors.clear()
        self._step_status.clear()
        self._last_failed_step = None

    def set_raise_on_error(self, enabled: bool = True) -> None:
        """设置在步骤出错时是否重新抛出异常（默认 False）。"""
        self.raise_on_error = bool(enabled)

    def set_step_cache(
        self,
        step_name: str,
        enabled: bool = True,
        attrs: Optional[List[str]] = None,
        persist_path: Optional[str] = None,
        watch_attrs: Optional[List[str]] = None,
    ) -> None:
        """配置指定步骤的缓存。

        参数:
            step_name: 步骤名称（方法名）
            enabled: 是否启用缓存
            attrs: 要缓存/恢复的属性列表（例如 ['df', 'pair_len']）
            persist_path: 若指定，则在执行后把缓存持久化到该文件（使用 pickle），并在下一次调用时优先从该文件加载
        """
        self._cache_config[step_name] = {
            "enabled": bool(enabled),
            "attrs": list(attrs or []),
            "persist_path": persist_path,
            "watch_attrs": list(watch_attrs or []),
        }

    def clear_cache(self, step_name: Optional[str] = None) -> None:
        """清除指定步骤或所有步骤的缓存。"""
        if step_name:
            self._cache.pop(step_name, None)
            self._cache_config.pop(step_name, None)
        else:
            self._cache.clear()
            self._cache_config.clear()

    def get_cached_result(self, step_name: str) -> Optional[Dict[str, object]]:
        """返回指定步骤的内存缓存字典（若存在）。"""
        return self._cache.get(step_name)

    def _concat_by_channel(self, values: List[np.ndarray]) -> np.ndarray:
        """
        将按通道的特征数组按 build_waveform_df 的顺序进行连接，
        保证与 df 的行顺序一致。
        """
        parts: List[np.ndarray] = []
        if self.pair_len is None:
            raise RuntimeError("配对长度未定义，请确认已成功结构化波形")
        for ch in range(self.n_channels):
            n = int(self.pair_len[ch])
            arr = np.asarray(values[ch])[:n]
            parts.append(arr)
        return np.concatenate(parts) if parts else np.array([], dtype=float)

    def add_features_to_dataframe(self, names: Optional[List[str]] = None, verbose: bool = True) -> "WaveformDataset":
        if self.df is None:
            raise RuntimeError("需要先调用 build_dataframe()")
        if not self.features:
            if verbose:
                print("[features] 没有可用的特征，可先调用 compute_registered_features()")
            return self
        target_names = names or list(self.features.keys())
        for name in target_names:
            vals = self.features.get(name)
            if vals is None:
                continue
            col = self._concat_by_channel(vals)
            if len(col) != len(self.df):
                # 保护：长度不一致则跳过，避免污染 df
                if verbose:
                    print(f"[features] 跳过列 {name}（长度 {len(col)} != df 行数 {len(self.df)}）")
                continue
            self.df[name] = col
            if verbose:
                print(f"[features] 已添加列: {name}")
        return self

    def _validate_data_dir(self):
        """验证数据目录是否存在。若启用了 DAQ 扫描，可在目录缺失时尝试从 DAQ 扫描获取运行信息。"""
        if not os.path.exists(self.data_dir):
            if not self.use_daq_scan:
                raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")

            # 尝试使用 DAQ 扫描/报告获取运行信息
            try:
                info = self.check_daq_status()
                if info is None:
                    raise FileNotFoundError(
                        f"数据目录 {self.data_dir} 不存在，DAQ 扫描也未发现运行 {self.char} (daq_root={self.daq_root})"
                    )
            except Exception:
                raise FileNotFoundError(f"数据目录不存在: {self.data_dir} 且无法从 DAQ 扫描获取信息")

    @chainable_step
    def load_raw_data(self, verbose: bool = True) -> "WaveformDataset":
        """
        加载原始 CSV 文件。若启用了 DAQ 集成，会优先尝试使用 DAQ 扫描结果/报告作为文件列表来源。

        返回: self（便于链式调用）
        """
        # 优先使用 DAQ 扫描信息（若启用）
        if self.use_daq_scan:
            try:
                self.check_daq_status()
            except Exception:
                # 若扫描失败，后续会回退到原始加载方式
                if verbose:
                    print(f"[{self.char}] 警告: 无法完成 DAQ 扫描，回退到常规文件收集方式")

            # 若有 DAQRun 对象（本地扫描），直接使用其文件路径信息
            if self.daq_run is not None and getattr(self.daq_run, "channel_files", None):
                max_ch = (
                    max(self.daq_run.channel_files.keys())
                    if self.daq_run.channel_files
                    else self.start_channel_slice + self.n_channels - 1
                )
                n = max(self.start_channel_slice + self.n_channels, max_ch + 1)
                raw_filess = [[] for _ in range(n)]
                for ch, files in self.daq_run.channel_files.items():
                    sorted_files = sorted(files, key=lambda x: x.get("index", 0))
                    raw_filess[ch] = [f["path"] for f in sorted_files]

                self.raw_files = raw_filess

                if verbose:
                    print(f"[{self.char}] 从 DAQ 扫描结果加载 {len(raw_filess)} 个通道文件信息")
                return self

            # 若加载自 JSON 报告
            if self.daq_info is not None:
                channel_details = self.daq_info.get("channel_details", {})
                run_path = self.daq_info.get("path", self.data_dir)
                max_ch = (
                    max(int(k) for k in channel_details.keys())
                    if channel_details
                    else self.start_channel_slice + self.n_channels - 1
                )
                n = max(self.start_channel_slice + self.n_channels, max_ch + 1)
                raw_filess = [[] for _ in range(n)]
                for ch_str, chdata in channel_details.items():
                    ch = int(ch_str)
                    files = chdata.get("files", [])
                    sorted_files = sorted(files, key=lambda x: x.get("index", 0))
                    raw_filess[ch] = [os.path.join(run_path, "RAW", f["filename"]) for f in sorted_files]

                self.raw_files = raw_filess

                if verbose:
                    print(f"[{self.char}] 从 DAQ 报告加载 {len(raw_filess)} 个通道文件信息")
                return self

        # 回退到默认的文件查找
        raw_filess = get_raw_files(n_channels=self.start_channel_slice + self.n_channels, char=self.char)
        self.raw_files = raw_filess

        if verbose:
            print(f"[{self.char}] 加载 {len(raw_filess)} 个通道的原始文件")
            for ch, fs in enumerate(raw_filess):
                print(f"  CH{ch}: {len(fs)} 个文件")

        return self

    @chainable_step
    def extract_waveforms(self, verbose: bool = True) -> "WaveformDataset":
        """
        从原始文件中提取波形数据。

        返回: self（便于链式调用）
        """
        if not self.load_waveforms:
            if verbose:
                print("  跳过波形提取（load_waveforms=False）")
            return self

        if not self.raw_files:
            raise RuntimeError("需要先调用 load_raw_data()")

        waveforms = get_waveforms(self.raw_files[self.start_channel_slice :])
        self.waveforms = waveforms

        if verbose:
            for ch, wf in enumerate(waveforms):
                if wf.size == 0:
                    print(f"  CH{self.start_channel_slice + ch}: 空数组")
                else:
                    print(f"  CH{self.start_channel_slice + ch}: {wf.shape}")

        return self

    @chainable_step
    def structure_waveforms(self, verbose: bool = True) -> "WaveformDataset":
        """
        将波形数据转换为结构化 numpy 数组（包含 baseline, timestamp, wave）。

        返回: self（便于链式调用）
        """
        if not self.load_waveforms:
            if verbose:
                print("  跳过波形结构化（load_waveforms=False）")
            return self

        if not self.waveforms:
            raise RuntimeError("需要先调用 extract_waveforms()")

        waveform_struct = WaveformStruct(self.waveforms)
        self.st_waveforms = waveform_struct.structrue_waveforms()
        self.pair_len = waveform_struct.get_pair_length()

        # 预构建 timestamp -> index 加速表
        self._build_timestamp_index()

        if verbose:
            print(f"结构化波形完成，配对长度: {self.pair_len}")
            for i in range(len(self.st_waveforms)):
                if len(self.st_waveforms[i]) > 0:
                    print(f"  通道 {i}: 字段 {list(self.st_waveforms[i].dtype.names)}")

        return self

    @chainable_step
    def build_waveform_features(
        self,
        peaks_range: Optional[Tuple[int, int]] = None,
        charge_range: Optional[Tuple[int, int]] = None,
        verbose: bool = True,
    ) -> "WaveformDataset":
        """
        计算波形特征（peaks 和 charges）。

        参数:
            peaks_range: peak 窗口 (start, end)
            charge_range: charge 窗口 (start, end)
            verbose: 是否打印日志

        返回: self（便于链式调用）
        """
        if not self.st_waveforms:
            raise RuntimeError("需要先调用 structure_waveforms()")
        if self.pair_len is None:
            raise RuntimeError("配对长度未定义，请确认已成功结构化波形")

        if peaks_range is not None:
            self.peaks_range = peaks_range
        if charge_range is not None:
            self.charge_range = charge_range

        start_p, end_p = self.peaks_range
        start_c, end_c = self.charge_range

        peaks = [
            np.array([
                np.max(wave["wave"][start_p:end_p]) - np.min(wave["wave"][start_p:end_p])
                for wave in self.st_waveforms[i]
            ])[: self.pair_len[i]]
            for i in range(len(self.st_waveforms))
        ]

        charges = [
            np.array([np.sum(wave["baseline"] - wave["wave"][start_c:end_c]) for wave in self.st_waveforms[i]])[
                : self.pair_len[i]
            ]
            for i in range(len(self.st_waveforms))
        ]

        self.peaks = peaks
        self.charges = charges

        # 也将这两类特征注册（便于扩展统一管理）
        def _peak_fn(_self, st_waveforms, pair_len, **params):
            return peaks

        def _charge_fn(_self, st_waveforms, pair_len, **params):
            return charges

        self.register_feature("peak", _peak_fn)
        self.register_feature("charge", _charge_fn)

        if verbose:
            for i, (p, q) in enumerate(zip(peaks, charges)):
                print(f"  通道 {i}: {len(p)} 个 peaks, {len(q)} 个 charges")

        return self

    @chainable_step
    def build_dataframe(self, verbose: bool = True) -> "WaveformDataset":
        """
        构建波形 DataFrame（单通道事件列表）。

        返回: self（便于链式调用）
        """
        if not self.peaks or not self.charges:
            raise RuntimeError("需要先调用 build_waveform_features()")

        self.df = build_waveform_df(
            self.st_waveforms, self.peaks, self.charges, self.pair_len, n_channels=self.n_channels
        )
        # 将注册特征（如有）落盘到 df
        if self.features or self.feature_fns:
            # 若尚未计算，先计算一次
            if not self.features:
                self.compute_registered_features(verbose=False)
            self.add_features_to_dataframe(verbose=False)
        self.df.sort_values("timestamp", inplace=True)

        if verbose:
            print(f"构建 DataFrame 完成，事件总数: {len(self.df)}")

        return self

    @chainable_step
    def group_events(self, time_window_ns: Optional[float] = None, verbose: bool = True) -> "WaveformDataset":
        """
        按时间窗口聚类多通道事件。

        参数:
            time_window_ns: 时间窗口（纳秒）
            verbose: 是否打印日志

        返回: self（便于链式调用）
        """
        if self.df is None:
            raise RuntimeError("需要先调用 build_dataframe()")

        if time_window_ns is not None:
            self.time_window_ns = time_window_ns

        self.df_events = group_multi_channel_hits(self.df, self.time_window_ns)

        if verbose:
            print(f"聚类完成，事件组数: {len(self.df_events)}")
            hit_counts = self.df_events["n_hits"].value_counts().sort_index()
            print(f"  事件类型分布:\n{hit_counts}")

        return self

    @chainable_step
    def pair_events(self, verbose: bool = True) -> "WaveformDataset":
        """
        筛选成对的 N 通道事件。

        返回: self（便于链式调用）
        """
        if self.df_events is None:
            raise RuntimeError("需要先调用 group_events()")

        df_paired = self.df_events[
            (self.df_events["n_hits"] == self.n_channels)
            & (self.df_events["channels"].apply(lambda x: np.array_equal(x, list(range(self.n_channels)))))
        ].copy()

        # 计算时间差（单位: ns）
        df_paired["delta_t"] = df_paired["timestamps"].apply(lambda x: (x[-1] - x[0]) / 1000.0)

        # 提取各通道的 charges 和 peaks
        for i in range(self.n_channels):
            df_paired[f"charge_ch{self.start_channel_slice + i}"] = df_paired["charges"].apply(lambda x: x[i])
            df_paired[f"peak_ch{self.start_channel_slice + i}"] = df_paired["peaks"].apply(lambda x: x[i])

        self.df_paired = df_paired

        if verbose:
            print(f"配对完成，成功配对的事件数: {len(self.df_paired)}")

        return self

    # 可插拔配对策略：允许自定义过滤规则
    def pair_events_with(
        self, strategy: Callable[[pd.DataFrame, int], pd.DataFrame], verbose: bool = True
    ) -> "WaveformDataset":
        """
        使用自定义策略对 df_events 进行配对过滤。

        参数:
            strategy(df_events, n_channels) -> DataFrame  返回配对后的 DataFrame
        """
        if self.df_events is None:
            raise RuntimeError("需要先调用 group_events()")

        df_paired = strategy(self.df_events, self.n_channels).copy()

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

        self.df_paired = df_paired

        if verbose:
            print(f"[strategy] 配对完成，成功配对的事件数: {len(self.df_paired)}")

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

    def get_waveform_at(self, event_idx: int, channel: int = 0) -> Optional[Tuple[np.ndarray, float]]:
        """
        获取指定事件和通道的原始波形及其 baseline。

        参数:
            event_idx: df_paired 中的事件索引
            channel: 通道索引（相对于 start_channel_slice）

        返回: (波形数组, baseline) 或 None
        """
        if not self.load_waveforms:
            print("⚠️  波形数据未加载（load_waveforms=False）")
            return None

        if self.df_paired is None or event_idx >= len(self.df_paired):
            return None

        event = self.df_paired.iloc[event_idx]
        ts = event["timestamps"][channel]

        # 使用预构建索引加速查找
        self._ensure_timestamp_index()
        idx_map = self._timestamp_index[channel] if channel < len(self._timestamp_index) else {}
        idx = idx_map.get(int(ts), -1)
        if idx == -1:
            return None

        try:
            wave = self.st_waveforms[channel][idx]["wave"]
            baseline = self.st_waveforms[channel][idx]["baseline"]
            return wave, baseline
        except (IndexError, ValueError):
            return None

    def save_results(self, output_dir: str = "outputs", verbose: bool = True) -> "WaveformDataset":
        """
        保存处理结果（CSV 和 Parquet 格式）。

        参数:
            output_dir: 输出目录
            verbose: 是否打印日志

        返回: self（便于链式调用）
        """
        os.makedirs(output_dir, exist_ok=True)

        if self.df_paired is not None and len(self.df_paired) > 0:
            csv_path = os.path.join(output_dir, f"{self.char}_paired.csv")
            pq_path = os.path.join(output_dir, f"{self.char}_paired.parquet")

            self.df_paired.to_csv(csv_path, index=False)
            self.df_paired.to_parquet(pq_path)

            if verbose:
                print(f"已保存: {csv_path}")
                print(f"已保存: {pq_path}")
        else:
            if verbose:
                print("没有配对事件，跳过保存")

        return self

    def summary(self) -> Dict[str, Any]:
        """
        获取数据处理摘要信息。

        返回: 包含各个处理阶段信息的字典
        """
        base = {
            "dataset": self.char,
            "n_channels": self.n_channels,
            "raw_files_count": sum(len(f) for f in self.raw_files) if self.raw_files else 0,
            "waveforms_shape": [w.shape if w.size > 0 else "empty" for w in self.waveforms],
            "raw_events": len(self.df) if self.df is not None else 0,
            "grouped_events": len(self.df_events) if self.df_events is not None else 0,
            "paired_events": len(self.df_paired) if self.df_paired is not None else 0,
            "features_config": {
                "peaks_range": self.peaks_range,
                "charge_range": self.charge_range,
                "time_window_ns": self.time_window_ns,
            },
        }

        # DAQ 相关信息（若启用且可用）
        daq_summary = {"enabled": bool(self.use_daq_scan), "found": False}

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
