# -*- coding: utf-8 -*-
"""
Dataset 模块 - 面向用户的高层 API 封装。

WaveformDataset 类作为框架的主要入口，通过链式调用 (Fluent Interface) 封装了
从数据加载到分析结果保存的完整流程。它内部委托 Context 进行插件调度，
在保持 API 简洁的同时，利用了插件系统的缓存和依赖管理能力。
"""

import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.core import standard_plugins
from waveform_analysis.core.context import Context
from waveform_analysis.core.foundation.mixins import CacheMixin, StepMixin, chainable_step


class WaveformDataset(CacheMixin, StepMixin):
    """
    统一的波形数据集容器，封装整个数据处理流程。
    支持链式调用，简化数据加载、预处理和分析。
    
    使用示例：
        dataset = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2)
        dataset.load_raw_data().extract_waveforms().structure_waveforms()\\
               .build_waveform_features().build_dataframe().group_events()\\
               .pair_events().save_results()
        
        df_paired = dataset.get_paired_events()
        summary = dataset.summary()
    """

    def __init__(
        self,
        run_name: str = "50V_OV_circulation_20thr",
        n_channels: int = 2,
        start_channel_slice: int = 6,
        data_root: str = "DAQ",
        load_waveforms: bool = True,
        use_daq_scan: bool = False,
        daq_root: Optional[str] = None,
        daq_report: Optional[str] = None,
        cache_waveforms: bool = True,
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化数据集。

        参数:
            run_name: 数据集标识符
            n_channels: 要处理的通道数
            start_channel_slice: 开始通道索引（通常为 6 表示 CH6/CH7）
            data_root: 数据根目录
            load_waveforms: 是否加载原始波形数据（默认 True）
                           - True: 加载所有波形，支持 get_waveform_at()
                           - False: 仅加载特征（峰值、电荷等），节省内存 (70-80% 内存节省)
            cache_waveforms: 是否缓存提取后的波形数据到磁盘（默认 True）
            cache_dir: 缓存目录，默认为 outputs/_cache
        """
        CacheMixin.__init__(self)
        StepMixin.__init__(self)

        # 兼容旧的 char 参数
        if "char" in kwargs:
            run_name = kwargs.pop("char")

        self.run_name = run_name
        self.char = run_name  # 保持 char 属性以兼容旧代码
        self.n_channels = n_channels
        self.start_channel_slice = start_channel_slice
        self.data_root = data_root
        self.data_dir = os.path.join(data_root, run_name)
        self.load_waveforms = load_waveforms
        self.cache_waveforms = cache_waveforms
        self.cache_dir = cache_dir or os.path.join("outputs", "_cache")

        # 初始化插件式 Context
        self.ctx = Context(storage_dir=self.cache_dir)
        self.ctx.register(standard_plugins)
        self.ctx.set_config({
            "n_channels": n_channels,
            "start_channel_slice": start_channel_slice,
            "data_root": data_root,
            "peaks_range": (40, 90),
            "charge_range": (60, 400),
            "time_window_ns": 100,
        })

        # DAQ 集成选项
        self.use_daq_scan = use_daq_scan
        self.daq_root = daq_root or data_root
        self.daq_report = daq_report
        self.daq_run = None
        self.daq_info = None

        # 数据容器
        self.raw_files: List[List[str]] = []
        self.waveforms: List[np.ndarray] = []
        self.st_waveforms: List[np.ndarray] = []

        # 特征和结果
        self.peaks: List[np.ndarray] = []
        self.charges: List[np.ndarray] = []
        self.df: Optional[pd.DataFrame] = None
        self.df_events: Optional[pd.DataFrame] = None
        self.df_paired: Optional[pd.DataFrame] = None

        # 缓存：timestamp -> index
        self._timestamp_index: List[Dict[int, int]] = []

        # 参数缓存
        self.peaks_range: Tuple[int, int] = (40, 90)
        self.charge_range: Tuple[int, int] = (60, 400)
        self.time_window_ns: float = 100

        self._validate_data_dir()

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
    def _ensure_timestamp_index(self):
        if not self._timestamp_index:
            self._build_timestamp_index()

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
            run = analyzer.get_run(self.run_name)
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
            if r.get("run_name") == self.run_name:
                self.daq_info = r
                self.daq_run = None
                return r
        return None

    # -------- 链式步骤相关工具 --------
    def clear_cache(
        self, 
        step_name: Optional[str] = None,
        clear_memory: bool = True,
        clear_disk: bool = True
    ) -> int:
        """
        清理缓存。
        
        参数:
            step_name: 步骤名称（如 "st_waveforms", "df"），如果为 None 则清理所有步骤
            clear_memory: 是否清理内存缓存
            clear_disk: 是否清理磁盘缓存
        
        返回:
            清理的缓存项数量
        
        示例:
            >>> ds = WaveformDataset(...)
            >>> # 清理单个步骤的缓存
            >>> ds.clear_cache("st_waveforms")
            >>> # 清理所有缓存
            >>> ds.clear_cache()
            >>> # 只清理内存缓存
            >>> ds.clear_cache("df", clear_disk=False)
        """
        return self.ctx.clear_cache_for(
            self.run_name, 
            step_name, 
            clear_memory=clear_memory,
            clear_disk=clear_disk
        )

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
                        f"数据目录 {self.data_dir} 不存在，DAQ 扫描也未发现运行 {self.run_name} (daq_root={self.daq_root})"
                    )
            except Exception:
                raise FileNotFoundError(f"数据目录不存在: {self.data_dir} 且无法从 DAQ 扫描获取信息")

    @chainable_step
    def load_raw_data(self, verbose: bool = True) -> "WaveformDataset":
        """
        加载原始 CSV 文件。
        """
        self.raw_files = self.ctx.get_data(self.run_name, "raw_files")

        if verbose:
            print(f"[{self.run_name}] 加载 {len(self.raw_files)} 个通道的原始文件")
        return self

    @chainable_step
    def extract_waveforms(self, verbose: bool = True, **kwargs) -> "WaveformDataset":
        """
        从原始文件中提取波形数据。
        """
        self.waveforms = self.ctx.get_data(self.run_name, "waveforms", **kwargs)

        if verbose:
            for ch, wf in enumerate(self.waveforms):
                if wf.size > 0:
                    print(f"  CH{self.start_channel_slice + ch}: {wf.shape}")
        return self

    def clear_waveforms(self) -> None:
        """释放波形相关的大块内存（waveforms 与 st_waveforms）。"""
        self.waveforms = []
        self.st_waveforms = []
        self._timestamp_index = []

    @chainable_step
    def structure_waveforms(self, verbose: bool = True) -> "WaveformDataset":
        """
        将波形数据转换为结构化 numpy 数组。
        """
        if not self.load_waveforms:
            return self

        self.st_waveforms = self.ctx.get_data(self.run_name, "st_waveforms")
        self._build_timestamp_index()

        if verbose:
            n_events = [len(st_ch) for st_ch in self.st_waveforms]
            print(f"结构化波形完成，各通道事件数: {n_events}")
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
        """
        if peaks_range:
            self.peaks_range = peaks_range
        if charge_range:
            self.charge_range = charge_range

        self.ctx.set_config({
            "peaks_range": self.peaks_range,
            "charge_range": self.charge_range,
        })

        self.peaks = self.ctx.get_data(self.run_name, "peaks")
        self.charges = self.ctx.get_data(self.run_name, "charges")

        if verbose:
            print(f"特征计算完成: {len(self.peaks)} 通道")
        return self

    @chainable_step
    def build_dataframe(self, verbose: bool = True) -> "WaveformDataset":
        """
        构建波形 DataFrame。
        """
        self.df = self.ctx.get_data(self.run_name, "df")

        if verbose:
            print(f"构建 DataFrame 完成，事件总数: {len(self.df)}")
        return self

    @chainable_step
    def group_events(
        self,
        time_window_ns: Optional[float] = None,
        use_numba: bool = True,
        n_processes: Optional[int] = None,
        verbose: bool = True,
    ) -> "WaveformDataset":
        """
        按时间窗口聚类多通道事件。
        
        参数:
            time_window_ns: 时间窗口（纳秒）
            use_numba: 是否使用numba加速（默认True）
            n_processes: 多进程数量（None=单进程，>1=多进程）
            verbose: 是否打印日志
        """
        tw = time_window_ns or self.time_window_ns
        self.ctx.set_config({
            "time_window_ns": tw,
            "use_numba": use_numba,
            "n_processes": n_processes,
        })
        self.df_events = self.ctx.get_data(self.run_name, "df_events")

        if time_window_ns:
            self.time_window_ns = time_window_ns

        if verbose:
            print(f"聚类完成，事件组数: {len(self.df_events)}")
            if n_processes and n_processes > 1:
                print(f"  使用 {n_processes} 个进程并行处理")
            elif use_numba:
                try:
                    import numba
                    print(f"  使用 numba 加速")
                except ImportError:
                    pass
        return self

    @chainable_step
    def pair_events(
        self, n_channels: Optional[int] = None, start_channel_slice: Optional[int] = None, verbose: bool = True
    ) -> "WaveformDataset":
        """
        筛选成对的 N 通道事件。
        """
        n_ch = n_channels or self.n_channels
        start_ch = start_channel_slice or self.start_channel_slice

        self.ctx.set_config({"n_channels": n_ch, "start_channel_slice": start_ch})
        self.df_paired = self.ctx.get_data(self.run_name, "df_paired")

        if verbose:
            print(f"配对完成，成功配对的事件数: {len(self.df_paired)}")
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
            csv_path = os.path.join(output_dir, f"{self.run_name}_paired.csv")
            pq_path = os.path.join(output_dir, f"{self.run_name}_paired.parquet")

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
            "dataset": self.run_name,
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
        run_name: str,
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
            run_name: 运行名
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
            run_name=run_name,
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
            f"WaveformDataset(run_name='{self.run_name}', n_channels={self.n_channels}, "
            f"raw_events={len(self.df) if self.df is not None else 0}, "
            f"paired_events={len(self.df_paired) if self.df_paired is not None else 0})"
        )
