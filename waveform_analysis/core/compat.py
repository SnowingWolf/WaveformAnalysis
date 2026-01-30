"""
兼容层 - 集中管理旧名称映射和单位转换。

提供：
1. 全局单位约定 (StandardUnits)
2. 旧配置名映射 (LEGACY_CONFIG_NAMES)
3. 旧字段名映射 (LEGACY_FIELD_NAMES)
4. 单位转换工具 (convert_time, convert_frequency, sampling_rate_to_interval)
5. 旧名称解析 (resolve_config_name, migrate_config)
"""

from typing import Any, Dict, Optional, Tuple
import warnings

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
class StandardUnits:
    """
    全局单位约定。

    定义系统中各类物理量的标准单位，确保一致性。

    Attributes:
        TIMESTAMP_UNIT: ADC 时间戳单位（皮秒）
        SYSTEM_TIME_UNIT: 系统时间单位（纳秒）
        SAMPLE_INTERVAL_UNIT: 采样间隔单位（纳秒）
        SAMPLING_RATE_UNIT: 采样率单位（Hz）

    Examples:
        >>> from waveform_analysis.core.compat import StandardUnits
        >>> StandardUnits.TIMESTAMP_UNIT
        'ps'
        >>> StandardUnits.convert_time(1.0, 'ns', 'ps')
        1000.0
    """

    # 标准单位定义
    TIMESTAMP_UNIT = "ps"  # ADC 时间戳：皮秒
    SYSTEM_TIME_UNIT = "ns"  # 系统时间：纳秒
    SAMPLE_INTERVAL_UNIT = "ns"  # 采样间隔：纳秒
    SAMPLING_RATE_UNIT = "Hz"  # 采样率：Hz

    # 时间单位转换到皮秒的系数
    TIME_TO_PS: Dict[str, float] = {
        "ps": 1.0,
        "ns": 1e3,
        "us": 1e6,
        "ms": 1e9,
        "s": 1e12,
    }

    # 时间单位转换到纳秒的系数
    TIME_TO_NS: Dict[str, float] = {
        "ps": 1e-3,
        "ns": 1.0,
        "us": 1e3,
        "ms": 1e6,
        "s": 1e9,
    }

    # 频率单位转换到 Hz 的系数
    FREQ_TO_HZ: Dict[str, float] = {
        "Hz": 1.0,
        "kHz": 1e3,
        "MHz": 1e6,
        "GHz": 1e9,
    }


# 旧配置名映射
# 格式: "old_name": ("new_name", "deprecation_message")
LEGACY_CONFIG_NAMES: Dict[str, Tuple[str, str]] = {
    # 示例（根据实际需要添加）:
    # "sample_rate": ("sampling_rate", "Use 'sampling_rate' instead of 'sample_rate'"),
}

# 旧字段名映射
# 格式: "old_field": ("new_field", "deprecation_message")
LEGACY_FIELD_NAMES: Dict[str, Tuple[str, str]] = {
    # 示例（根据实际需要添加）:
    # "ts": ("timestamp", "Use 'timestamp' instead of 'ts'"),
}


@export
def convert_time(value: float, from_unit: str, to_unit: str) -> float:
    """
    转换时间单位。

    Args:
        value: 要转换的值
        from_unit: 源单位 ('ps', 'ns', 'us', 'ms', 's')
        to_unit: 目标单位 ('ps', 'ns', 'us', 'ms', 's')

    Returns:
        转换后的值

    Raises:
        ValueError: 不支持的单位

    Examples:
        >>> convert_time(1.0, 'ns', 'ps')
        1000.0
        >>> convert_time(1000.0, 'ps', 'ns')
        1.0
    """
    if from_unit not in StandardUnits.TIME_TO_PS:
        raise ValueError(f"Unsupported time unit: {from_unit}")
    if to_unit not in StandardUnits.TIME_TO_PS:
        raise ValueError(f"Unsupported time unit: {to_unit}")

    # 先转换到皮秒，再转换到目标单位
    value_in_ps = value * StandardUnits.TIME_TO_PS[from_unit]
    return value_in_ps / StandardUnits.TIME_TO_PS[to_unit]


@export
def convert_frequency(value: float, from_unit: str, to_unit: str) -> float:
    """
    转换频率单位。

    Args:
        value: 要转换的值
        from_unit: 源单位 ('Hz', 'kHz', 'MHz', 'GHz')
        to_unit: 目标单位 ('Hz', 'kHz', 'MHz', 'GHz')

    Returns:
        转换后的值

    Raises:
        ValueError: 不支持的单位

    Examples:
        >>> convert_frequency(1.0, 'GHz', 'MHz')
        1000.0
        >>> convert_frequency(1000.0, 'MHz', 'GHz')
        1.0
    """
    if from_unit not in StandardUnits.FREQ_TO_HZ:
        raise ValueError(f"Unsupported frequency unit: {from_unit}")
    if to_unit not in StandardUnits.FREQ_TO_HZ:
        raise ValueError(f"Unsupported frequency unit: {to_unit}")

    # 先转换到 Hz，再转换到目标单位
    value_in_hz = value * StandardUnits.FREQ_TO_HZ[from_unit]
    return value_in_hz / StandardUnits.FREQ_TO_HZ[to_unit]


@export
def sampling_rate_to_interval(rate_hz: float, interval_unit: str = "ns") -> float:
    """
    将采样率转换为采样间隔。

    Args:
        rate_hz: 采样率（Hz）
        interval_unit: 输出间隔的单位，默认 'ns'

    Returns:
        采样间隔

    Raises:
        ValueError: 采样率为零或负数，或不支持的单位

    Examples:
        >>> sampling_rate_to_interval(1e9, 'ns')  # 1 GHz -> 1 ns
        1.0
        >>> sampling_rate_to_interval(1e9, 'ps')  # 1 GHz -> 1000 ps
        1000.0
    """
    if rate_hz <= 0:
        raise ValueError(f"Sampling rate must be positive, got {rate_hz}")

    # 计算间隔（秒）
    interval_s = 1.0 / rate_hz

    # 转换到目标单位
    return convert_time(interval_s, "s", interval_unit)


@export
def interval_to_sampling_rate(interval: float, interval_unit: str = "ns") -> float:
    """
    将采样间隔转换为采样率。

    Args:
        interval: 采样间隔
        interval_unit: 间隔的单位，默认 'ns'

    Returns:
        采样率（Hz）

    Raises:
        ValueError: 间隔为零或负数，或不支持的单位

    Examples:
        >>> interval_to_sampling_rate(1.0, 'ns')  # 1 ns -> 1 GHz
        1000000000.0
        >>> interval_to_sampling_rate(1000.0, 'ps')  # 1000 ps -> 1 GHz
        1000000000.0
    """
    if interval <= 0:
        raise ValueError(f"Interval must be positive, got {interval}")

    # 转换到秒
    interval_s = convert_time(interval, interval_unit, "s")

    return 1.0 / interval_s


@export
def resolve_config_name(name: str, warn: bool = True) -> str:
    """
    解析配置名，将旧名称映射到新名称。

    Args:
        name: 配置名
        warn: 是否发出弃用警告，默认 True

    Returns:
        解析后的配置名（如果是旧名称则返回新名称，否则原样返回）

    Examples:
        >>> # 假设 LEGACY_CONFIG_NAMES 中有 "sample_rate" -> "sampling_rate"
        >>> resolve_config_name("sample_rate")  # 会发出警告
        'sampling_rate'
        >>> resolve_config_name("threshold")  # 不在映射中，原样返回
        'threshold'
    """
    if name in LEGACY_CONFIG_NAMES:
        new_name, message = LEGACY_CONFIG_NAMES[name]
        if warn:
            warnings.warn(
                f"Config name '{name}' is deprecated. {message}",
                DeprecationWarning,
                stacklevel=3,
            )
        return new_name
    return name


@export
def resolve_field_name(name: str, warn: bool = True) -> str:
    """
    解析字段名，将旧名称映射到新名称。

    Args:
        name: 字段名
        warn: 是否发出弃用警告，默认 True

    Returns:
        解析后的字段名（如果是旧名称则返回新名称，否则原样返回）

    Examples:
        >>> # 假设 LEGACY_FIELD_NAMES 中有 "ts" -> "timestamp"
        >>> resolve_field_name("ts")  # 会发出警告
        'timestamp'
    """
    if name in LEGACY_FIELD_NAMES:
        new_name, message = LEGACY_FIELD_NAMES[name]
        if warn:
            warnings.warn(
                f"Field name '{name}' is deprecated. {message}",
                DeprecationWarning,
                stacklevel=3,
            )
        return new_name
    return name


@export
def migrate_config(config: Dict[str, Any], warn: bool = True) -> Dict[str, Any]:
    """
    迁移配置字典，将所有旧配置名替换为新名称。

    支持嵌套字典（插件命名空间配置）。

    Args:
        config: 原始配置字典
        warn: 是否发出弃用警告，默认 True

    Returns:
        迁移后的配置字典（新字典，不修改原始配置）

    Examples:
        >>> # 假设 LEGACY_CONFIG_NAMES 中有 "sample_rate" -> "sampling_rate"
        >>> migrate_config({"sample_rate": 1e9, "threshold": 50})
        {'sampling_rate': 1000000000.0, 'threshold': 50}

        >>> # 支持嵌套配置
        >>> migrate_config({"my_plugin": {"sample_rate": 1e9}})
        {'my_plugin': {'sampling_rate': 1000000000.0}}
    """
    migrated = {}

    for key, value in config.items():
        # 解析顶层键名
        new_key = resolve_config_name(key, warn=warn)

        if isinstance(value, dict):
            # 递归处理嵌套字典（插件命名空间）
            migrated[new_key] = migrate_config(value, warn=warn)
        else:
            migrated[new_key] = value

    return migrated


@export
def add_legacy_config_mapping(old_name: str, new_name: str, message: Optional[str] = None) -> None:
    """
    添加旧配置名映射。

    用于在运行时动态注册旧名称映射。

    Args:
        old_name: 旧配置名
        new_name: 新配置名
        message: 弃用提示信息（可选）

    Examples:
        >>> add_legacy_config_mapping("sample_rate", "sampling_rate")
        >>> add_legacy_config_mapping(
        ...     "old_param",
        ...     "new_param",
        ...     "Use 'new_param' for better clarity"
        ... )
    """
    if message is None:
        message = f"Use '{new_name}' instead of '{old_name}'"
    LEGACY_CONFIG_NAMES[old_name] = (new_name, message)


@export
def add_legacy_field_mapping(old_name: str, new_name: str, message: Optional[str] = None) -> None:
    """
    添加旧字段名映射。

    用于在运行时动态注册旧字段名映射。

    Args:
        old_name: 旧字段名
        new_name: 新字段名
        message: 弃用提示信息（可选）

    Examples:
        >>> add_legacy_field_mapping("ts", "timestamp")
    """
    if message is None:
        message = f"Use '{new_name}' instead of '{old_name}'"
    LEGACY_FIELD_NAMES[old_name] = (new_name, message)
