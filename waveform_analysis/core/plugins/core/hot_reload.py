# -*- coding: utf-8 -*-
"""
插件热重载模块 (Phase 3.3)

提供插件的热重载功能,无需重启即可更新插件代码:
- 监控插件文件变化
- 自动重载插件
- 保持缓存数据一致性
- 版本管理
"""

import hashlib
import importlib
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Type

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Plugin

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# 插件热重载
# ===========================

@export
class PluginHotReloader:
    """
    插件热重载器

    监控插件文件变化并自动重载

    使用示例:
        reloader = PluginHotReloader(ctx)
        reloader.watch_plugin('my_plugin', 'path/to/plugin.py')
        reloader.enable_auto_reload()  # 启动自动重载
    """

    def __init__(self, context: Any):
        """
        初始化重载器

        Args:
            context: Context对象
        """
        self.context = context
        self.watched_plugins: Dict[str, Dict[str, Any]] = {}  # {plugin_name: {path, mtime, hash, ...}}
        self.auto_reload_enabled = False
        self.logger = logging.getLogger(self.__class__.__name__)

    def watch_plugin(
        self,
        plugin_name: str,
        plugin_path: Optional[str] = None,
        plugin_class: Optional[Type[Plugin]] = None
    ):
        """
        添加插件到监控列表

        Args:
            plugin_name: 插件名称
            plugin_path: 插件文件路径
            plugin_class: 插件类
        """
        if plugin_name not in self.context._plugins:
            raise ValueError(f"Plugin '{plugin_name}' not registered in context")

        # 获取插件信息
        plugin = self.context._plugins[plugin_name]

        if plugin_path is None:
            # 尝试从插件类获取路径
            try:
                plugin_module = sys.modules[plugin.__class__.__module__]
                plugin_path = plugin_module.__file__
            except Exception as e:
                self.logger.warning(f"Cannot determine plugin path for '{plugin_name}': {e}")
                return

        if plugin_path and os.path.exists(plugin_path):
            self.watched_plugins[plugin_name] = {
                'path': plugin_path,
                'mtime': os.path.getmtime(plugin_path),
                'hash': self._compute_file_hash(plugin_path),
                'plugin_class': plugin_class or plugin.__class__,
            }
            self.logger.info(f"Watching plugin '{plugin_name}' at {plugin_path}")
        else:
            self.logger.warning(f"Plugin path not found: {plugin_path}")

    def check_updates(self) -> List[str]:
        """
        检查插件是否有更新

        Returns:
            有更新的插件名称列表
        """
        updated_plugins = []

        for plugin_name, info in self.watched_plugins.items():
            path = info['path']

            if not os.path.exists(path):
                self.logger.warning(f"Plugin file not found: {path}")
                continue

            current_mtime = os.path.getmtime(path)
            current_hash = self._compute_file_hash(path)

            if current_mtime > info['mtime'] or current_hash != info['hash']:
                updated_plugins.append(plugin_name)
                self.logger.info(f"Plugin '{plugin_name}' has been modified")

        return updated_plugins

    def reload_plugin(self, plugin_name: str, clear_cache: bool = True):
        """
        重载插件

        Args:
            plugin_name: 插件名称
            clear_cache: 是否清除该插件的缓存
        """
        if plugin_name not in self.watched_plugins:
            raise ValueError(f"Plugin '{plugin_name}' is not being watched")

        info = self.watched_plugins[plugin_name]
        path = info['path']

        try:
            # 重载模块
            module_name = self._get_module_name(path)
            if module_name in sys.modules:
                module = sys.modules[module_name]
                importlib.reload(module)
                self.logger.info(f"Reloaded module: {module_name}")
            else:
                # 导入新模块
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self.logger.info(f"Loaded module: {module_name}")

            # 获取新的插件类
            plugin_class = info.get('plugin_class')
            if plugin_class is None:
                # 尝试从模块中找到Plugin子类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                        plugin_class = attr
                        break

            if plugin_class is None:
                raise ValueError(f"Cannot find Plugin class in {path}")

            # 创建新插件实例
            new_plugin = plugin_class()

            # 重新注册插件(允许覆盖)
            # 注意：register_plugin 会自动调用 _invalidate_caches_for 清除性能缓存
            self.context.register(new_plugin, allow_override=True)

            # 清除性能缓存（register_plugin 已自动清除，这里是为了日志记录）
            if clear_cache:
                # register_plugin 已经通过 _invalidate_caches_for 清除了相关缓存
                # 如果需要清除数据缓存（_results），请使用 clear_cache_for(run_id, data_name)
                self.logger.info(f"Cache invalidated for plugin '{plugin_name}' (via register_plugin)")

            # 更新监控信息
            info['mtime'] = os.path.getmtime(path)
            info['hash'] = self._compute_file_hash(path)

            self.logger.info(f"Successfully reloaded plugin '{plugin_name}'")

        except Exception as e:
            self.logger.error(f"Failed to reload plugin '{plugin_name}': {e}")
            raise

    def reload_all_updated(self, clear_cache: bool = True):
        """
        重载所有有更新的插件

        Args:
            clear_cache: 是否清除缓存
        """
        updated_plugins = self.check_updates()

        for plugin_name in updated_plugins:
            try:
                self.reload_plugin(plugin_name, clear_cache=clear_cache)
            except Exception as e:
                self.logger.error(f"Failed to reload '{plugin_name}': {e}")

    def enable_auto_reload(self, interval: float = 2.0):
        """
        启用自动重载(注意:这是一个简单的轮询实现)

        Args:
            interval: 检查间隔(秒)
        """
        self.auto_reload_enabled = True
        self.logger.info(f"Auto-reload enabled with {interval}s interval")

        # 注意:实际应用中应该使用watchdog等库进行文件系统监控
        # 这里只是一个简单的示例
        import threading

        def check_loop():
            while self.auto_reload_enabled:
                try:
                    self.reload_all_updated(clear_cache=True)
                except Exception as e:
                    self.logger.error(f"Error in auto-reload: {e}")
                time.sleep(interval)

        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start()

    def disable_auto_reload(self):
        """禁用自动重载"""
        self.auto_reload_enabled = False
        self.logger.info("Auto-reload disabled")

    def _compute_file_hash(self, path: str) -> str:
        """计算文件的hash值"""
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()

    def _get_module_name(self, path: str) -> str:
        """从文件路径获取模块名"""
        path = Path(path)
        return f"hot_reload_{path.stem}_{int(time.time())}"


@export
def enable_hot_reload(
    context: Any,
    plugin_names: Optional[List[str]] = None,
    auto_reload: bool = True,
    interval: float = 2.0
) -> PluginHotReloader:
    """
    为Context启用插件热重载

    Args:
        context: Context对象
        plugin_names: 要监控的插件名称列表,None表示所有插件
        auto_reload: 是否启用自动重载
        interval: 自动重载检查间隔

    Returns:
        PluginHotReloader实例

    Examples:
        >>> reloader = enable_hot_reload(ctx, ['my_plugin'])
        >>> # 插件文件修改后会自动重载
    """
    reloader = PluginHotReloader(context)

    # 添加插件到监控
    if plugin_names is None:
        plugin_names = list(context._plugins.keys())

    for plugin_name in plugin_names:
        try:
            reloader.watch_plugin(plugin_name)
        except Exception as e:
            logger.warning(f"Cannot watch plugin '{plugin_name}': {e}")

    # 启用自动重载
    if auto_reload:
        reloader.enable_auto_reload(interval=interval)

    return reloader
