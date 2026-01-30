# DOC: docs/features/context/CONFIGURATION.md#适配器推断
"""
Adapter 推断信息

提供从 DAQ adapter 提取配置推断信息的功能。
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
@dataclass
class AdapterInfo:
    """DAQ Adapter 推断信息

    封装从 DAQ adapter 提取的配置信息，用于自动推断插件配置值。

    Attributes:
        name: adapter 名称（如 "vx2730"）
        sampling_rate_hz: 采样率（Hz）
        timestamp_unit: 时间戳单位（如 "ps", "ns"）
        dt_ns: 采样间隔（纳秒）
        dt_ps: 采样间隔（皮秒）
        expected_samples: 预期采样点数

    Examples:
        >>> info = AdapterInfo.from_adapter("vx2730")
        >>> print(info.sampling_rate_hz)
        500000000.0
        >>> print(info.dt_ns)
        2
    """

    name: str
    sampling_rate_hz: float
    timestamp_unit: str
    dt_ns: int
    dt_ps: int
    expected_samples: Optional[int] = None

    @classmethod
    def from_adapter(cls, adapter_name: str) -> Optional["AdapterInfo"]:
        """从 adapter 名称创建 AdapterInfo

        Args:
            adapter_name: DAQ adapter 名称

        Returns:
            AdapterInfo 实例，如果 adapter 不存在则返回 None

        Examples:
            >>> info = AdapterInfo.from_adapter("vx2730")
            >>> info.sampling_rate_hz
            500000000.0
        """
        try:
            from waveform_analysis.utils.formats import get_adapter, is_adapter_registered

            if not is_adapter_registered(adapter_name):
                return None

            adapter = get_adapter(adapter_name)
            spec = adapter.format_spec

            # 计算采样间隔
            sampling_rate = spec.sampling_rate_hz or 500e6  # 默认 500 MHz
            dt_ns = int(1e9 / sampling_rate)  # 纳秒
            dt_ps = int(1e12 / sampling_rate)  # 皮秒

            # 获取时间戳单位
            timestamp_unit = spec.timestamp_unit.value if spec.timestamp_unit else "ps"

            return cls(
                name=adapter_name,
                sampling_rate_hz=sampling_rate,
                timestamp_unit=timestamp_unit,
                dt_ns=dt_ns,
                dt_ps=dt_ps,
                expected_samples=spec.expected_samples,
            )
        except Exception:
            return None

    @classmethod
    def from_adapter_object(cls, adapter) -> Optional["AdapterInfo"]:
        """从 DAQAdapter 对象创建 AdapterInfo

        Args:
            adapter: DAQAdapter 实例

        Returns:
            AdapterInfo 实例
        """
        try:
            spec = adapter.format_spec

            # 计算采样间隔
            sampling_rate = spec.sampling_rate_hz or 500e6
            dt_ns = int(1e9 / sampling_rate)
            dt_ps = int(1e12 / sampling_rate)

            # 获取时间戳单位
            timestamp_unit = spec.timestamp_unit.value if spec.timestamp_unit else "ps"

            return cls(
                name=adapter.name,
                sampling_rate_hz=sampling_rate,
                timestamp_unit=timestamp_unit,
                dt_ns=dt_ns,
                dt_ps=dt_ps,
                expected_samples=spec.expected_samples,
            )
        except Exception:
            return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含所有属性的字典
        """
        return {
            "name": self.name,
            "sampling_rate_hz": self.sampling_rate_hz,
            "timestamp_unit": self.timestamp_unit,
            "dt_ns": self.dt_ns,
            "dt_ps": self.dt_ps,
            "expected_samples": self.expected_samples,
        }

    def get_inferred_value(self, key: str) -> Optional[Any]:
        """获取可推断的配置值

        Args:
            key: 配置键名

        Returns:
            推断的值，如果无法推断则返回 None
        """
        mapping = {
            "sampling_rate_hz": self.sampling_rate_hz,
            "sampling_rate": self.sampling_rate_hz,
            "dt_ns": self.dt_ns,
            "dt_ps": self.dt_ps,
            "timestamp_unit": self.timestamp_unit,
            "expected_samples": self.expected_samples,
        }
        return mapping.get(key)

    def __repr__(self) -> str:
        return (
            f"AdapterInfo(name='{self.name}', "
            f"sampling_rate_hz={self.sampling_rate_hz}, "
            f"timestamp_unit='{self.timestamp_unit}')"
        )


# 预定义的 adapter 信息（用于快速查找，避免重复解析）
_ADAPTER_INFO_CACHE: Dict[str, AdapterInfo] = {}


@export
def get_adapter_info(adapter_name: str, use_cache: bool = True) -> Optional[AdapterInfo]:
    """获取 adapter 信息（带缓存）

    Args:
        adapter_name: adapter 名称
        use_cache: 是否使用缓存

    Returns:
        AdapterInfo 实例或 None
    """
    if use_cache and adapter_name in _ADAPTER_INFO_CACHE:
        return _ADAPTER_INFO_CACHE[adapter_name]

    info = AdapterInfo.from_adapter(adapter_name)
    if info and use_cache:
        _ADAPTER_INFO_CACHE[adapter_name] = info

    return info


@export
def clear_adapter_info_cache() -> None:
    """清除 adapter 信息缓存"""
    _ADAPTER_INFO_CACHE.clear()
