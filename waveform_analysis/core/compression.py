"""
压缩后端模块 - 为存储系统提供可插拔的压缩支持

本模块提供了统一的压缩后端接口(CompressionBackend Protocol)以及多种具体实现:
- Blosc2Compression: numpy优化的高速压缩(优先推荐)
- LZ4Compression: 极快速度的压缩
- ZstdCompression: 平衡的压缩算法
- GzipCompression: 标准库提供的基础压缩

设计原则:
1. 所有压缩库都是可选依赖,缺失时graceful degradation
2. 优先考虑读写速度而非压缩比
3. 对numpy structured arrays提供shuffle优化
4. 透明的压缩/解压,用户无感知
"""

import logging
import warnings
from typing import Protocol, Optional, Dict, Any, Type
import numpy as np

from waveform_analysis.core.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# Compression Backend Protocol
# ===========================

class CompressionBackend(Protocol):
    """压缩后端的统一接口"""

    @property
    def name(self) -> str:
        """压缩算法名称"""
        ...

    @property
    def extension(self) -> str:
        """文件扩展名,如 '.blosc2', '.lz4'"""
        ...

    @property
    def speed_priority(self) -> str:
        """速度优先级: 'fast' | 'balanced' | 'max_compression'"""
        ...

    def compress(self, data: bytes) -> bytes:
        """压缩数据"""
        ...

    def decompress(self, data: bytes) -> bytes:
        """解压数据"""
        ...

    def is_available(self) -> bool:
        """检查压缩库是否可用"""
        ...


# ===========================
# Blosc2 Compression (优先推荐)
# ===========================

@export
class Blosc2Compression:
    """
    基于blosc2的压缩后端,专为numpy数组优化

    特点:
    - 多线程压缩/解压
    - Shuffle优化提升压缩比
    - 针对数值数据优化
    - 速度极快

    使用场景: numpy structured arrays, 大规模数值数据
    """

    def __init__(
        self,
        cname: str = 'zstd',  # 内部codec: blosclz, lz4, lz4hc, zlib, zstd
        clevel: int = 5,       # 压缩级别 0-9
        shuffle: int = 2,      # 0=no shuffle, 1=byte shuffle, 2=bit shuffle
        nthreads: int = 4,     # 压缩线程数
    ):
        self.cname = cname
        self.clevel = clevel
        self.shuffle = shuffle
        self.nthreads = nthreads
        self._blosc2 = None

        # 尝试导入blosc2
        try:
            import blosc2
            self._blosc2 = blosc2
            # 设置线程数
            blosc2.set_nthreads(nthreads)
        except ImportError:
            logger.warning("blosc2 not available. Install with: pip install blosc2")

    @property
    def name(self) -> str:
        return f"blosc2-{self.cname}"

    @property
    def extension(self) -> str:
        return ".blosc2"

    @property
    def speed_priority(self) -> str:
        return "fast"

    def is_available(self) -> bool:
        return self._blosc2 is not None

    def compress(self, data: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("blosc2 is not available")

        return self._blosc2.compress(
            data,
            codec=self._blosc2.Codec[self.cname.upper()] if hasattr(self._blosc2, 'Codec') else self.cname,
            clevel=self.clevel,
            shuffle=self.shuffle,
        )

    def decompress(self, data: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("blosc2 is not available")

        return self._blosc2.decompress(data)

    def compress_array(self, arr: np.ndarray) -> bytes:
        """
        直接压缩numpy数组,自动启用shuffle优化

        对于structured arrays,shuffle能显著提升压缩比
        """
        if not self.is_available():
            raise RuntimeError("blosc2 is not available")

        # 使用numpy的tobytes()获取C连续内存
        data = np.ascontiguousarray(arr).tobytes()

        # 对于structured arrays,使用bit shuffle效果最佳
        shuffle = 2 if arr.dtype.names else self.shuffle

        return self._blosc2.compress(
            data,
            codec=self._blosc2.Codec[self.cname.upper()] if hasattr(self._blosc2, 'Codec') else self.cname,
            clevel=self.clevel,
            shuffle=shuffle,
        )


# ===========================
# LZ4 Compression (极速)
# ===========================

@export
class LZ4Compression:
    """
    基于LZ4的压缩后端,速度优先

    特点:
    - 解压速度极快(GB/s级别)
    - 压缩速度快
    - 压缩比较低

    使用场景: 需要极快读取速度的场景,如实时数据处理
    """

    def __init__(self, compression_level: int = 0):
        """
        Args:
            compression_level: 0=快速, 9=高压缩(HC模式)
        """
        self.compression_level = compression_level
        self._lz4 = None

        try:
            import lz4.frame
            self._lz4 = lz4.frame
        except ImportError:
            logger.warning("lz4 not available. Install with: pip install lz4")

    @property
    def name(self) -> str:
        return f"lz4-{self.compression_level}"

    @property
    def extension(self) -> str:
        return ".lz4"

    @property
    def speed_priority(self) -> str:
        return "fast"

    def is_available(self) -> bool:
        return self._lz4 is not None

    def compress(self, data: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("lz4 is not available")

        return self._lz4.compress(
            data,
            compression_level=self.compression_level,
        )

    def decompress(self, data: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("lz4 is not available")

        return self._lz4.decompress(data)


# ===========================
# Zstd Compression (平衡)
# ===========================

@export
class ZstdCompression:
    """
    基于Zstandard的压缩后端,平衡压缩比和速度

    特点:
    - 压缩比高
    - 速度较快
    - 内存占用低

    使用场景: 存储空间有限,但也需要合理的读写速度
    """

    def __init__(self, level: int = 3, threads: int = 0):
        """
        Args:
            level: 压缩级别 1-22 (推荐3-9)
            threads: 压缩线程数,0表示自动
        """
        self.level = level
        self.threads = threads
        self._zstd = None

        try:
            import zstandard as zstd
            self._zstd = zstd
        except ImportError:
            logger.warning("zstandard not available. Install with: pip install zstandard")

    @property
    def name(self) -> str:
        return f"zstd-{self.level}"

    @property
    def extension(self) -> str:
        return ".zst"

    @property
    def speed_priority(self) -> str:
        return "balanced"

    def is_available(self) -> bool:
        return self._zstd is not None

    def compress(self, data: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("zstandard is not available")

        cctx = self._zstd.ZstdCompressor(
            level=self.level,
            threads=self.threads,
        )
        return cctx.compress(data)

    def decompress(self, data: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("zstandard is not available")

        dctx = self._zstd.ZstdDecompressor()
        return dctx.decompress(data)


# ===========================
# Gzip Compression (标准库后备)
# ===========================

@export
class GzipCompression:
    """
    基于gzip的压缩后端,标准库提供

    特点:
    - 无需额外依赖
    - 兼容性好
    - 速度较慢
    - 压缩比中等

    使用场景: 无法安装额外依赖时的后备选项
    """

    def __init__(self, compresslevel: int = 6):
        """
        Args:
            compresslevel: 压缩级别 1-9
        """
        self.compresslevel = compresslevel

    @property
    def name(self) -> str:
        return f"gzip-{self.compresslevel}"

    @property
    def extension(self) -> str:
        return ".gz"

    @property
    def speed_priority(self) -> str:
        return "balanced"

    def is_available(self) -> bool:
        return True  # 标准库总是可用

    def compress(self, data: bytes) -> bytes:
        import gzip
        return gzip.compress(data, compresslevel=self.compresslevel)

    def decompress(self, data: bytes) -> bytes:
        import gzip
        return gzip.decompress(data)


# ===========================
# Compression Manager
# ===========================

@export
class CompressionManager:
    """
    压缩管理器,负责选择和管理压缩后端

    使用示例:
        manager = CompressionManager()
        backend = manager.get_backend('blosc2')  # 自动fallback到可用的
        compressed = backend.compress(data)
    """

    # 按优先级排序(基于速度)
    _BACKEND_PRIORITY = ['blosc2', 'lz4', 'zstd', 'gzip']

    def __init__(self):
        self._backends: Dict[str, Type] = {
            'blosc2': Blosc2Compression,
            'lz4': LZ4Compression,
            'zstd': ZstdCompression,
            'gzip': GzipCompression,
        }
        self._instances: Dict[str, Any] = {}

    def get_backend(
        self,
        name: Optional[str] = None,
        fallback: bool = True,
        **kwargs
    ) -> Any:
        """
        获取压缩后端实例

        Args:
            name: 压缩算法名称,None表示使用第一个可用的
            fallback: 如果指定的不可用,是否fallback到其他可用的
            **kwargs: 传递给压缩后端的参数

        Returns:
            压缩后端实例

        Raises:
            RuntimeError: 没有可用的压缩后端
        """
        if name is None:
            # 使用第一个可用的
            name = self._get_first_available()

        # 检查缓存
        cache_key = f"{name}_{hash(frozenset(kwargs.items()))}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        # 创建实例
        if name not in self._backends:
            if fallback:
                warnings.warn(f"Unknown compression backend '{name}', using fallback")
                name = self._get_first_available()
            else:
                raise ValueError(f"Unknown compression backend: {name}")

        backend_cls = self._backends[name]
        instance = backend_cls(**kwargs)

        # 检查是否可用
        if not instance.is_available():
            if fallback:
                warnings.warn(
                    f"Compression backend '{name}' not available, trying fallback"
                )
                name = self._get_first_available(exclude=[name])
                backend_cls = self._backends[name]
                instance = backend_cls(**kwargs)
            else:
                raise RuntimeError(f"Compression backend '{name}' is not available")

        # 缓存实例
        self._instances[cache_key] = instance
        return instance

    def _get_first_available(self, exclude: Optional[list] = None) -> str:
        """获取第一个可用的压缩后端名称"""
        exclude = exclude or []

        for name in self._BACKEND_PRIORITY:
            if name in exclude:
                continue

            backend_cls = self._backends[name]
            instance = backend_cls()

            if instance.is_available():
                return name

        raise RuntimeError("No compression backend available")

    def list_available(self) -> list:
        """列出所有可用的压缩后端"""
        available = []
        for name in self._BACKEND_PRIORITY:
            backend_cls = self._backends[name]
            instance = backend_cls()
            if instance.is_available():
                available.append({
                    'name': name,
                    'speed_priority': instance.speed_priority,
                    'extension': instance.extension,
                })
        return available

    def benchmark(
        self,
        data: bytes,
        backends: Optional[list] = None,
        repeats: int = 3
    ) -> Dict[str, Dict[str, float]]:
        """
        对比不同压缩算法的性能

        Args:
            data: 测试数据
            backends: 要测试的后端列表,None表示所有可用的
            repeats: 重复次数

        Returns:
            每个后端的统计信息 {backend_name: {compress_time, decompress_time, ratio}}
        """
        import time

        if backends is None:
            backends = [b['name'] for b in self.list_available()]

        results = {}

        for name in backends:
            try:
                backend = self.get_backend(name, fallback=False)
            except (ValueError, RuntimeError):
                continue

            # Benchmark compression
            compress_times = []
            compressed_data = None
            for _ in range(repeats):
                start = time.perf_counter()
                compressed_data = backend.compress(data)
                compress_times.append(time.perf_counter() - start)

            # Benchmark decompression
            decompress_times = []
            for _ in range(repeats):
                start = time.perf_counter()
                backend.decompress(compressed_data)
                decompress_times.append(time.perf_counter() - start)

            results[name] = {
                'compress_time_ms': np.mean(compress_times) * 1000,
                'decompress_time_ms': np.mean(decompress_times) * 1000,
                'compression_ratio': len(data) / len(compressed_data),
                'compressed_size_mb': len(compressed_data) / (1024 * 1024),
            }

        return results


# 全局单例
_compression_manager = None

@export
def get_compression_manager() -> CompressionManager:
    """获取全局CompressionManager单例"""
    global _compression_manager
    if _compression_manager is None:
        _compression_manager = CompressionManager()
    return _compression_manager
