"""
WaveformAnalysis 全局常量定义

此模块定义了系统中使用的所有魔术数字和配置常量，
避免硬编码值分散在代码库中，提高可维护性。
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
class FeatureDefaults:
    """特征提取的默认参数

    这些常量用于波形特征计算，如峰值、电荷、基线等。
    修改这些值会影响所有使用默认参数的特征计算。
    """

    # 峰值计算的采样点范围 (起始, 结束)
    PEAK_RANGE = (40, 90)

    # 电荷计算的采样点范围 (起始, 结束；结束为 None 表示波形末端)
    CHARGE_RANGE = (0, None)

    # 基线计算的采样点范围 (起始, 结束)
    BASELINE_RANGE = (0, 20)

    # 事件分组的时间窗口 (纳秒)
    TIME_WINDOW_NS = 100

    # 峰值查找的最小间隔 (采样点数)
    MIN_PEAK_DISTANCE = 10

    # 峰值检测的最小高度阈值
    MIN_PEAK_HEIGHT = 0.01


@export
class ProcessingDefaults:
    """数据处理的默认参数

    这些常量控制数据加载、分块、缓存等底层处理行为。
    """

    # 分块处理的默认块大小 (事件数)
    CHUNK_SIZE = 50000

    # I/O 缓冲区大小 (字节)
    BUFFER_SIZE = 4 * 1024 * 1024  # 4MB

    # Memmap 模式
    MEMMAP_MODE = "r"  # 只读模式

    # 并行处理的默认工作线程数
    DEFAULT_WORKERS = 4

    # 缓存过期时间 (秒)
    CACHE_EXPIRY_SECONDS = 3600  # 1小时


@export
class StorageDefaults:
    """存储相关的默认参数"""

    # 存储版本号
    STORAGE_VERSION = "1.0.0"

    # 文件锁超时 (秒)
    LOCK_TIMEOUT = 10.0

    # 文件锁重试间隔 (秒)
    LOCK_RETRY_INTERVAL = 0.1

    # 压缩级别 (0-9，0表示不压缩)
    COMPRESSION_LEVEL = 3

    # 最大重试次数
    MAX_RETRIES = 3


@export
class ValidationDefaults:
    """数据验证的默认参数"""

    # 时间戳单调性检查的容差 (纳秒)
    TIME_MONOTONIC_TOLERANCE = 1.0

    # 块边界检查的容差 (纳秒)
    CHUNK_BOUNDARY_TOLERANCE = 0.001

    # 允许的最大内存使用 (字节)
    MAX_MEMORY_USAGE = 8 * 1024 * 1024 * 1024  # 8GB


@export
class VisualizationDefaults:
    """可视化的默认参数"""

    # 默认图形大小 (英寸)
    FIGURE_SIZE = (12, 8)

    # 默认 DPI
    DPI = 100

    # 默认颜色映射
    COLORMAP = "viridis"

    # 血缘图节点宽度
    LINEAGE_NODE_WIDTH = 3.0

    # 血缘图节点高度
    LINEAGE_NODE_HEIGHT = 1.5


# 导出所有常量类
__all__.extend([
    "FeatureDefaults",
    "ProcessingDefaults",
    "StorageDefaults",
    "ValidationDefaults",
    "VisualizationDefaults",
])
