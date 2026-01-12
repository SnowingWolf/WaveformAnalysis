# -*- coding: utf-8 -*-
"""
Plugin Loader 模块 - 动态插件发现和加载系统

支持：
- 基于 entry points 的插件发现
- 从指定目录加载插件
- 插件元数据验证
- 延迟加载和错误处理
"""

import importlib
import importlib.util
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Type

from waveform_analysis.core.foundation.utils import exporter

# 初始化 exporter
export, __all__ = exporter()

logger = logging.getLogger(__name__)


@export
class PluginLoader:
    """
    插件加载器 - 负责发现和加载插件

    特性:
    - Entry points 支持（通过 importlib.metadata）
    - 目录扫描支持
    - 自动插件验证
    - 错误处理和日志
    """

    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        """
        初始化插件加载器

        Args:
            plugin_dirs: 额外的插件目录列表
        """
        self.plugin_dirs = plugin_dirs or []
        self._discovered_plugins: Dict[str, Type] = {}
        self._failed_plugins: Dict[str, str] = {}  # name -> error message

    def discover_entry_point_plugins(self, group: str = 'waveform_analysis.plugins') -> int:
        """
        从 entry points 发现插件

        Args:
            group: Entry point 组名

        Returns:
            发现的插件数量
        """
        try:
            from importlib.metadata import entry_points
        except ImportError:
            # Python < 3.10
            try:
                from importlib_metadata import entry_points
            except ImportError:
                logger.warning("importlib.metadata not available, skipping entry point discovery")
                return 0

        count = 0
        eps = entry_points()

        # 兼容不同版本的 importlib.metadata
        if hasattr(eps, 'select'):
            # Python 3.10+
            group_eps = eps.select(group=group)
        elif hasattr(eps, 'get'):
            # Python 3.9
            group_eps = eps.get(group, [])
        else:
            # Older versions - eps is a dict
            group_eps = eps.get(group, [])

        for ep in group_eps:
            try:
                plugin_class = ep.load()

                # 验证是插件类
                if self._validate_plugin_class(plugin_class):
                    self._discovered_plugins[ep.name] = plugin_class
                    count += 1
                    logger.info(f"Discovered plugin '{ep.name}' from entry point")
                else:
                    self._failed_plugins[ep.name] = "Not a valid Plugin class"
                    logger.warning(f"Entry point '{ep.name}' is not a valid Plugin class")

            except Exception as e:
                self._failed_plugins[ep.name] = str(e)
                logger.error(f"Failed to load plugin '{ep.name}' from entry point: {e}")

        return count

    def discover_directory_plugins(self, directory: str) -> int:
        """
        从目录发现插件

        支持两种结构:
        1. plugin.py 文件（单文件插件）
        2. __init__.py 文件（包插件）

        Args:
            directory: 插件目录路径

        Returns:
            发现的插件数量
        """
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            logger.warning(f"Plugin directory does not exist: {directory}")
            return 0

        count = 0

        # 查找所有 plugin.py 和 __init__.py
        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            # 跳过隐藏目录和 __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

            # 检查 plugin.py
            if 'plugin.py' in files:
                plugin_path = root_path / 'plugin.py'
                count += self._load_module_plugins(str(plugin_path), root_path.name)

            # 检查 __init__.py（包插件）
            elif '__init__.py' in files and root_path != path:
                plugin_path = root_path / '__init__.py'
                count += self._load_module_plugins(str(plugin_path), root_path.name)

        return count

    def _load_module_plugins(self, module_path: str, module_name: str) -> int:
        """
        从模块文件加载插件

        Args:
            module_path: 模块文件路径
            module_name: 模块名称

        Returns:
            加载的插件数量
        """
        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create module spec for {module_path}")
                return 0

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找所有插件类
            count = 0

            for attr_name in dir(module):
                if attr_name.startswith('_'):
                    continue

                attr = getattr(module, attr_name)
                if self._validate_plugin_class(attr):
                    plugin_name = f"{module_name}.{attr_name}"
                    self._discovered_plugins[plugin_name] = attr
                    count += 1
                    logger.info(f"Discovered plugin '{plugin_name}' from {module_path}")

            return count

        except Exception as e:
            logger.error(f"Failed to load plugins from {module_path}: {e}")
            self._failed_plugins[module_name] = str(e)
            return 0

    def _validate_plugin_class(self, obj) -> bool:
        """
        验证对象是否为有效的插件类

        Args:
            obj: 待验证对象

        Returns:
            是否为有效插件类
        """
        try:
            from waveform_analysis.core.plugins.core.base import Plugin
            import inspect

            return (
                inspect.isclass(obj) and
                issubclass(obj, Plugin) and
                obj != Plugin and
                hasattr(obj, 'provides') and
                hasattr(obj, 'compute')
            )
        except Exception:
            return False

    def get_plugins(self) -> List[Type]:
        """
        获取所有发现的插件类

        Returns:
            插件类列表
        """
        return list(self._discovered_plugins.values())

    def get_plugin_names(self) -> List[str]:
        """
        获取所有发现的插件名称

        Returns:
            插件名称列表
        """
        return list(self._discovered_plugins.keys())

    def get_failed_plugins(self) -> Dict[str, str]:
        """
        获取加载失败的插件及其错误信息

        Returns:
            {插件名: 错误信息} 字典
        """
        return self._failed_plugins.copy()

    def discover_all(self) -> int:
        """
        执行完整的插件发现流程

        发现顺序：
        1. Entry points
        2. 配置的插件目录

        Returns:
            总共发现的插件数量
        """
        total = 0

        # 1. Entry points
        total += self.discover_entry_point_plugins()

        # 2. 插件目录
        for plugin_dir in self.plugin_dirs:
            total += self.discover_directory_plugins(plugin_dir)

        logger.info(f"Plugin discovery complete: {total} plugins found, "
                   f"{len(self._failed_plugins)} failed")

        return total


@export
def load_plugins_from_entry_points(group: str = 'waveform_analysis.plugins') -> List[Type]:
    """
    便捷函数：从 entry points 加载插件

    Args:
        group: Entry point 组名

    Returns:
        插件类列表
    """
    loader = PluginLoader()
    loader.discover_entry_point_plugins(group)
    return loader.get_plugins()


@export
def load_plugins_from_directory(directory: str) -> List[Type]:
    """
    便捷函数：从目录加载插件

    Args:
        directory: 插件目录路径

    Returns:
        插件类列表
    """
    loader = PluginLoader([directory])
    loader.discover_directory_plugins(directory)
    return loader.get_plugins()
