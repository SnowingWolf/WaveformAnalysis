"""Data models used by plugin reference generation."""

from dataclasses import dataclass, field
from typing import Any

from .catalog import (
    CATEGORY_DISPLAY_NAMES,
    DOCUMENTATION_DEFAULT_PROFILE,
    DOCUMENTATION_PLUGIN_DEFAULTS,
)


@dataclass
class ConfigOptionInfo:
    """配置选项信息"""

    name: str
    type: str
    default: Any
    units: str | None = None
    doc: str = ""
    deprecated: bool = False
    tracked: bool = True
    internal_units: str | None = None
    choices: list[Any] = field(default_factory=list)
    min_value: Any = None
    max_value: Any = None
    deprecated_message: str = ""
    alias: str | None = None


@dataclass
class OutputFieldInfo:
    """输出字段信息"""

    name: str
    dtype: str
    units: str | None = None
    doc: str = ""


@dataclass
class DependencyDocumentationInfo:
    """Human-readable details for one plugin dependency."""

    name: str
    version_constraint: str = ""
    resolution: str = "declared"
    required_fields: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class PluginDocumentationView:
    """从插件提取的文档信息"""

    name: str  # 类名
    provides: str  # 数据名
    version: str  # 版本
    description: str  # 描述
    category: str  # 类别 (data_loading, features, events...)
    depends_on: list[Any] = field(default_factory=list)  # 类声明的依赖列表
    resolved_depends_on: list[Any] = field(default_factory=list)  # 文档默认画像下的依赖列表
    dependency_profile: str = ""
    dependency_profile_values: dict[str, Any] = field(default_factory=dict)
    dependency_config_keys: list[str] = field(default_factory=list)
    config_options: list[ConfigOptionInfo] = field(default_factory=list)  # 配置选项
    output_fields: list[OutputFieldInfo] = field(default_factory=list)  # 输出字段
    output_kind: str = "structured_array"  # 输出类型
    execution_kind: str = "static"  # static/stream 执行模式
    save_when: str = "never"
    uses_run_config: bool = False
    timeout: float | None = None
    input_requirements: dict[str, list[str]] = field(default_factory=dict)
    supports_streaming: bool = False
    supports_parallel: bool = True
    supports_gpu: bool = False
    is_side_effect: bool = False
    module_path: str = ""  # 模块路径
    module_doc: str = ""
    dependency_details: list[DependencyDocumentationInfo] = field(default_factory=list)
    resolved_dependency_details: list[DependencyDocumentationInfo] = field(default_factory=list)
    workflow_steps: list[str] = field(default_factory=list)
    execution_chain: list[str] = field(default_factory=list)
    execution_notes: list[str] = field(default_factory=list)
    output_summary: str = ""
    has_dynamic_dependencies: bool = False
    behavior_notes: list[str] = field(default_factory=list)
    field_notes: dict[str, str] = field(default_factory=dict)
    config_notes: dict[str, str] = field(default_factory=dict)
    cluster_contract: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    downstream_consumers: list[str] = field(default_factory=list)
    downstream_notes: list[str] = field(default_factory=list)
    agent_change_notes: list[str] = field(default_factory=list)
    overview: str = ""
    overview_paragraphs: list[str] = field(default_factory=list)
    usage_example: str = ""
    documentation_status: Any = None
    source_fingerprint: str | None = None
    documentation_completeness: int | None = None
    dag_impact: int | None = None
    workflow_diagram: str = ""  # mermaid flowchart 源码（插件内部处理流程）

    @property
    def category_display(self) -> str:
        """获取类别显示名称"""
        return CATEGORY_DISPLAY_NAMES.get(self.category, self.category)

    @property
    def module_import_path(self) -> str:
        """模块路径，去掉尾部 '.plugin' 段，用于生成 import 语句。"""
        parts = self.module_path.split(".")
        if parts and parts[-1] == "plugin":
            return ".".join(parts[:-1])
        return self.module_path

    @property
    def summary(self) -> str:
        return " ".join(self.description.split())


# Compatibility import for callers that used the old internal data-class name.
PluginDocInfo = PluginDocumentationView


@dataclass(frozen=True)
class _PluginSetDocumentation:
    """A canonical execution plugin set used by documentation facts."""

    name: str
    label: str
    plugins: list[PluginDocumentationView]
    description: str = ""


class _DefaultDocumentationContext:
    """Restricted context for resolving documentation-only default dependencies."""

    def __init__(self, plugins: dict[str, Any], *, shared_profile=None, plugin_profile=None):
        self._plugins = plugins
        self._shared_profile = dict(shared_profile or DOCUMENTATION_DEFAULT_PROFILE)
        self._plugin_profile = {
            name: dict(values)
            for name, values in (plugin_profile or DOCUMENTATION_PLUGIN_DEFAULTS).items()
        }
        self.config = {**self._shared_profile, **self._plugin_profile}

    def get_config(self, plugin: Any, key: str) -> Any:
        provides = str(getattr(plugin, "provides", ""))
        if key in self._plugin_profile.get(provides, {}):
            return self._plugin_profile[provides][key]
        if key in self._shared_profile:
            return self._shared_profile[key]
        option = getattr(plugin, "options", {}).get(key)
        if option is None:
            raise KeyError(f"Unknown documentation config option {provides}.{key}")
        return option.default
