"""
Cache 模块 - 缓存管理与签名校验。

提供 CacheManager 用于计算数据签名（基于文件修改时间和大小），
支持血缘追踪 (Lineage) 校验，确保当原始数据或处理逻辑发生变化时，缓存能自动失效。
"""

import hashlib
import os
from typing import Any, Dict, List, Optional

from .utils import exporter

# 初始化 exporter
export, __all__ = exporter()

# 用于标识缓存数据中的监视签名的键
WATCH_SIG_KEY = "__watch_sig__"
__all__.append("WATCH_SIG_KEY")


@export
class CacheManager:
    """
    缓存管理器 - 提供缓存数据的加载、保存和签名计算功能。
    """

    @staticmethod
    def get_key(step_name: str, char: str = "", **params) -> str:
        """
        生成缓存键。

        Args:
            step_name: 步骤名称
            char: 运行名称
            **params: 影响缓存的其他参数

        Returns:
            缓存键字符串
        """
        parts = [step_name, char]
        for k, v in sorted(params.items()):
            parts.append(f"{k}={v}")
        combined = "|".join(parts)
        return hashlib.sha1(combined.encode()).hexdigest()

    @staticmethod
    def compute_watch_signature(obj: Any, watch_attrs: List[str]) -> str:
        """
        计算监视属性的签名，用于检测数据是否发生变化。

        签名基于文件的 mtime 和 size 计算 SHA1 哈希。

        Args:
            obj: 拥有监视属性的对象
            watch_attrs: 要监视的属性名列表

        Returns:
            签名字符串（SHA1 哈希）
        """
        sig_parts = []
        for attr in watch_attrs:
            val = getattr(obj, attr, None)
            if val is None:
                sig_parts.append(f"{attr}:None")
            elif isinstance(val, str) and os.path.exists(val):
                # 如果是文件路径，计算文件的 mtime 和 size
                try:
                    stat = os.stat(val)
                    sig_parts.append(f"{attr}:{stat.st_mtime}:{stat.st_size}")
                except OSError:
                    sig_parts.append(f"{attr}:error")
            elif isinstance(val, (list, tuple)):
                # 如果是文件列表（支持嵌套列表）
                def _get_file_sig(item):
                    if isinstance(item, str) and os.path.exists(item):
                        try:
                            stat = os.stat(item)
                            return f"{stat.st_mtime}:{stat.st_size}"
                        except OSError:
                            return "error"
                    elif isinstance(item, (list, tuple)):
                        return f"[{','.join([_get_file_sig(i) for i in item])}]"
                    else:
                        return str(item)

                file_sigs = [_get_file_sig(item) for item in val]
                sig_parts.append(f"{attr}:[{','.join(file_sigs)}]")
            else:
                # 其他类型，使用字符串表示
                sig_parts.append(f"{attr}:{str(val)}")

        combined = "|".join(sig_parts)
        return hashlib.sha1(combined.encode()).hexdigest()

    @staticmethod
    def save_data(path: str, data: Dict[str, Any], backend: str = "joblib") -> bool:
        """
        保存缓存数据到磁盘。

        Args:
            path: 保存路径
            data: 要保存的数据字典
            backend: 序列化后端，支持 'joblib' 或 'pickle'

        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None

            if backend == "joblib":
                import joblib

                joblib.dump(data, path)
            elif backend == "pickle":
                import pickle

                with open(path, "wb") as f:
                    pickle.dump(data, f)
            else:
                raise ValueError(f"Unsupported backend: {backend}")
            return True
        except Exception as e:
            import warnings

            warnings.warn(f"Failed to save cache to {path}: {e}")
            return False

    @staticmethod
    def load_data(path: str, backend: str = "joblib") -> Optional[Dict[str, Any]]:
        """
        从磁盘加载缓存数据。

        Args:
            path: 文件路径
            backend: 序列化后端，支持 'joblib' 或 'pickle'

        Returns:
            加载的数据字典，如果加载失败则返回 None
        """
        if not os.path.exists(path):
            return None

        try:
            if backend == "joblib":
                import joblib

                return joblib.load(path)
            elif backend == "pickle":
                import pickle

                with open(path, "rb") as f:
                    return pickle.load(f)
            else:
                raise ValueError(f"Unsupported backend: {backend}")
        except Exception as e:
            import warnings

            warnings.warn(f"Failed to load cache from {path}: {e}")
            return None

    @staticmethod
    def delete_cache(path: str) -> bool:
        """
        删除缓存文件。

        Args:
            path: 文件路径

        Returns:
            是否删除成功
        """
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception:
            return False
