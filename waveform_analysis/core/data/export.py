"""
批量处理和数据导出模块

提供多运行批量处理和统一的数据导出功能:
- 批量处理多个run
- 统一的导出接口(Parquet, HDF5, CSV, JSON等)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.utils import exporter

from .batch_processor import BatchProcessor

logger = logging.getLogger(__name__)
export, __all__ = exporter()

BatchProcessor = export(BatchProcessor)


@export
class DataExporter:
    """
    统一的数据导出接口

    支持多种格式: Parquet, HDF5, CSV, JSON, NumPy

    使用示例:
        exporter = DataExporter()
        exporter.export(data, 'output.parquet', format='parquet')
    """

    SUPPORTED_FORMATS = ["parquet", "hdf5", "h5", "csv", "json", "npy", "npz"]

    def __init__(self):
        """初始化导出器"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def export(self, data, output_path: Union[str, Path], format: Optional[str] = None, **kwargs):
        """
        导出数据

        Args:
            data: 要导出的数据
            output_path: 输出文件路径
            format: 格式('parquet', 'hdf5', 'csv', 'json', 'npy', 'npz')
                   如果为None,从文件扩展名推断
            **kwargs: 格式特定的参数
        """
        output_path = Path(output_path)

        # 推断格式
        if format is None:
            format = output_path.suffix.lstrip(".")

        format = format.lower()

        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}")

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 根据格式导出
        if format == "parquet":
            self._export_parquet(data, output_path, **kwargs)
        elif format == "hdf5" or format == "h5":
            self._export_hdf5(data, output_path, **kwargs)
        elif format == "csv":
            self._export_csv(data, output_path, **kwargs)
        elif format == "json":
            self._export_json(data, output_path, **kwargs)
        elif format == "npy":
            self._export_npy(data, output_path, **kwargs)
        elif format == "npz":
            self._export_npz(data, output_path, **kwargs)

        self.logger.info(f"Exported data to {output_path} (format: {format})")

    def _export_parquet(self, data, output_path, **kwargs):
        """导出为Parquet格式"""
        df = self._to_dataframe(data)
        df.to_parquet(output_path, **kwargs)

    def _export_hdf5(self, data, output_path, key="data", **kwargs):
        """导出为HDF5格式"""
        df = self._to_dataframe(data)
        df.to_hdf(output_path, key=key, mode="w", **kwargs)

    def _export_csv(self, data, output_path, **kwargs):
        """导出为CSV格式"""
        df = self._to_dataframe(data)
        df.to_csv(output_path, index=False, **kwargs)

    def _export_json(self, data, output_path, **kwargs):
        """导出为JSON格式"""
        if isinstance(data, pd.DataFrame):
            data.to_json(output_path, **kwargs)
        elif isinstance(data, dict):
            import json

            with open(output_path, "w") as f:
                json.dump(data, f, **kwargs)
        else:
            df = self._to_dataframe(data)
            df.to_json(output_path, **kwargs)

    def _export_npy(self, data, output_path, **kwargs):
        """导出为NumPy .npy格式"""
        if isinstance(data, pd.DataFrame):
            data = data.to_records(index=False)
        np.save(output_path, data, **kwargs)

    def _export_npz(self, data, output_path, **kwargs):
        """导出为NumPy .npz格式"""
        if isinstance(data, dict):
            np.savez(output_path, **data, **kwargs)
        elif isinstance(data, pd.DataFrame):
            # 将DataFrame的每一列保存为独立的数组
            arrays = {col: data[col].values for col in data.columns}
            np.savez(output_path, **arrays, **kwargs)
        else:
            np.savez(output_path, data=data, **kwargs)

    def _to_dataframe(self, data) -> pd.DataFrame:
        """将数据转换为DataFrame"""
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, list) and all(isinstance(x, np.ndarray) for x in data):
            frames = []
            for idx, arr in enumerate(data):
                if arr.dtype.names:
                    df = pd.DataFrame(arr)
                else:
                    df = pd.DataFrame({"data": arr})
                if "channel" not in df.columns:
                    df.insert(0, "channel", idx)
                frames.append(df)
            if not frames:
                return pd.DataFrame()
            return pd.concat(frames, ignore_index=True)
        elif isinstance(data, np.ndarray):
            if data.dtype.names:
                # 结构化数组
                return pd.DataFrame(data)
            else:
                # 普通数组
                return pd.DataFrame({"data": data})
        elif isinstance(data, dict):
            return pd.DataFrame(data)
        else:
            raise TypeError(f"Cannot convert {type(data)} to DataFrame")


@export
def batch_export(
    context: Any,
    run_ids: List[str],
    data_name: str,
    output_dir: Union[str, Path],
    format: str = "parquet",
    max_workers: Optional[int] = None,
):
    """
    批量导出多个run的数据

    Args:
        context: Context对象
        run_ids: 运行ID列表
        data_name: 数据名称
        output_dir: 输出目录
        format: 导出格式
        max_workers: 最大并行工作进程数
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = BatchProcessor(context)
    exporter = DataExporter()

    # 批量获取数据
    batch_results = processor.process_runs(
        run_ids=run_ids, data_name=data_name, max_workers=max_workers, show_progress=True
    )

    # 导出每个run的数据
    for run_id, data in batch_results["results"].items():
        output_path = output_dir / f"{run_id}_{data_name}.{format}"
        try:
            exporter.export(data, output_path, format=format)
        except Exception as e:
            logger.error(f"Failed to export {run_id}: {e}")

    print(f"\nExported {len(batch_results['results'])} runs to {output_dir}")
