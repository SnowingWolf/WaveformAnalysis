"""Package-version resolution kept behind the root package's lazy boundary."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version


def resolve_package_version() -> str:
    """从包元数据读取版本，并保留源码树运行时的回退值。"""
    try:
        return package_version("waveform-analysis")
    except PackageNotFoundError:
        # 未安装分发包时（如直接源码运行）提供可解析回退版本。
        return "0.0.0+unknown"


__version__ = resolve_package_version()

__all__ = ["__version__"]
