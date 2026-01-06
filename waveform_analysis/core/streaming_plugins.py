"""
流式处理插件示例 - 展示如何使用 StreamingPlugin

这些插件演示了如何将现有处理逻辑转换为流式处理。
"""

from typing import Any, Iterator

import numpy as np

from .chunk_utils import Chunk, get_endtime
from .streaming import StreamingPlugin
from .utils import exporter

export, __all__ = exporter()


class StreamingStWaveformsPlugin(StreamingPlugin):
    """
    流式结构化波形插件示例。
    
    将原始波形数据流转换为结构化波形流。
    """
    
    provides = "st_waveforms_stream"
    depends_on = ["waveforms"]
    description = "Stream structured waveforms from raw waveforms"
    
    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        """
        处理单个 chunk：将原始波形转换为结构化波形。
        
        Args:
            chunk: 输入 chunk（包含原始波形数据）
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数
            
        Returns:
            结构化波形 chunk
        """
        from .processor import WaveformStruct, RECORD_DTYPE
        
        # 假设 chunk.data 是波形数组列表
        if isinstance(chunk.data, list):
            waveforms = chunk.data
        elif isinstance(chunk.data, np.ndarray):
            # 如果是单个数组，需要根据实际情况处理
            waveforms = [chunk.data]
        else:
            # 其他类型，跳过
            return None
        
        # 结构化处理
        struct = WaveformStruct(waveforms)
        st_waveforms = struct.structure_waveforms(show_progress=False)
        
        # 合并所有通道的结构化数据
        if len(st_waveforms) > 0:
            # 合并为单个数组
            merged = np.concatenate(st_waveforms) if len(st_waveforms) > 1 else st_waveforms[0]
            
            # 计算时间范围
            if len(merged) > 0 and "time" in merged.dtype.names:
                time = merged["time"]
                endtime = get_endtime(merged)
                start_time = int(np.min(time))
                end_time = int(np.max(endtime))
            else:
                start_time = chunk.start
                end_time = chunk.end
            
            return Chunk(
                data=merged,
                start=start_time,
                end=end_time,
                run_id=run_id,
                data_type=self.provides,
            )
        
        return None


class StreamingBasicFeaturesPlugin(StreamingPlugin):
    """
    流式基础特征插件示例。
    
    从结构化波形流计算峰值和电荷。
    """
    
    provides = "basic_features_stream"
    depends_on = ["st_waveforms_stream"]
    description = "Stream basic features (peaks and charges) from structured waveforms"
    
    def __init__(self):
        super().__init__()
        self.peaks_range = (40, 90)
        self.charge_range = (60, 400)
    
    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        """
        处理单个 chunk：计算峰值和电荷。
        
        Args:
            chunk: 输入 chunk（结构化波形）
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数
            
        Returns:
            特征 chunk（包含峰值和电荷）
        """
        from .processor import WaveformProcessor
        
        if len(chunk.data) == 0:
            return None
        
        # 计算特征（不再需要 event_length，直接使用全部数据）
        processor = WaveformProcessor(n_channels=1)  # 简化：单通道
        peaks, charges = processor.compute_basic_features(
            [chunk.data],
            self.peaks_range,
            self.charge_range,
        )
        
        # 创建特征数组
        feature_dtype = np.dtype([
            ("time", "<i8"),
            ("peak", "<f4"),
            ("charge", "<f4"),
        ])
        
        n = len(peaks[0])
        features = np.zeros(n, dtype=feature_dtype)
        features["time"] = chunk.data["time"][:n] if "time" in chunk.data.dtype.names else np.arange(n)
        features["peak"] = peaks[0]
        features["charge"] = charges[0]
        
        return Chunk(
            data=features,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )


class StreamingFilterPlugin(StreamingPlugin):
    """
    流式过滤插件示例。
    
    根据条件过滤 chunk 中的数据。
    """
    
    provides = "filtered_stream"
    depends_on = ["basic_features_stream"]
    description = "Filter chunks based on conditions"
    
    def __init__(self):
        super().__init__()
        self.min_charge = 0.0
        self.max_charge = np.inf
    
    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        """
        过滤 chunk：只保留满足条件的数据。
        
        Args:
            chunk: 输入 chunk
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数
            
        Returns:
            过滤后的 chunk
        """
        if len(chunk.data) == 0:
            return None
        
        # 应用过滤条件
        if "charge" in chunk.data.dtype.names:
            mask = (chunk.data["charge"] >= self.min_charge) & (chunk.data["charge"] <= self.max_charge)
            filtered_data = chunk.data[mask]
        else:
            # 没有 charge 字段，返回原数据
            filtered_data = chunk.data
        
        if len(filtered_data) == 0:
            return None
        
        # 计算新的时间范围
        if "time" in filtered_data.dtype.names:
            time = filtered_data["time"]
            endtime = get_endtime(filtered_data) if "endtime" in filtered_data.dtype.names else time
            start_time = int(np.min(time))
            end_time = int(np.max(endtime))
        else:
            start_time = chunk.start
            end_time = chunk.end
        
        return Chunk(
            data=filtered_data,
            start=start_time,
            end=end_time,
            run_id=run_id,
            data_type=self.provides,
        )

