# -*- coding: utf-8 -*-
"""
插件契约规范（Plugin Specification）

定义插件的机器可读契约，包括：
- 输入/输出 schema
- 配置规范
- 版本与能力声明

用于：
- 注册时校验插件完整性
- 生成文档
- 缓存一致性（lineage hash）
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .base import Option

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
@dataclass(frozen=True)
class ConfigField:
    """配置字段规范

    声明式配置规范，与 Option（运行时验证）形成互补：
    - Option: 运行时配置验证和类型转换
    - ConfigField: 静态契约声明，用于文档生成、lineage hash、IDE 提示

    Attributes:
        type: 类型名称（如 'float', 'int', 'str', 'bool'）
        default: 默认值
        doc: 说明文档
        units: 物理单位（如 'ns', 'mV', 'Hz'）
        track: 是否纳入 lineage（默认 True）
        deprecated: 弃用信息（如 "Use 'new_option' instead"）
        alias_of: 别名指向的规范键名
    """

    type: str = "any"
    default: Any = None
    doc: str = ""
    units: Optional[str] = None
    track: bool = True
    deprecated: Optional[str] = None
    alias_of: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "type": self.type,
            "default": self.default,
            "doc": self.doc,
            "units": self.units,
            "track": self.track,
            "deprecated": self.deprecated,
            "alias_of": self.alias_of,
        }

    @classmethod
    def from_option(cls, opt: "Option") -> "ConfigField":
        """从 Option 实例创建 ConfigField

        Args:
            opt: Option 实例

        Returns:
            ConfigField 实例
        """
        return cls(
            type=opt.type.__name__ if opt.type else "any",
            default=opt.default,
            doc=opt.help or "",
            track=getattr(opt, "track", True),
        )


@export
@dataclass(frozen=True)
class FieldSpec:
    """输出字段规范

    描述结构化数组中单个字段的元信息。

    Attributes:
        name: 字段名称
        dtype: NumPy dtype 字符串（如 'f8', 'i4', '<U64'）
        units: 物理单位（如 'ns', 'mV', 'Hz'）
        doc: 字段说明
        required: 是否必须存在于输出中
    """

    name: str
    dtype: str
    units: Optional[str] = None
    doc: str = ""
    required: bool = True


@export
@dataclass(frozen=True)
class OutputSchema:
    """输出数据 schema

    描述插件输出的完整结构。

    Attributes:
        fields: 字段规范列表
        dtype: 完整的 NumPy dtype（可选，用于结构化数组）
        kind: 输出类型（'array', 'structured_array', 'dict', 'list'）
        doc: schema 说明
    """

    fields: Tuple[FieldSpec, ...] = ()
    dtype: Optional[str] = None
    kind: str = "structured_array"
    doc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "fields": [
                {
                    "name": f.name,
                    "dtype": f.dtype,
                    "units": f.units,
                    "doc": f.doc,
                    "required": f.required,
                }
                for f in self.fields
            ],
            "dtype": self.dtype,
            "kind": self.kind,
            "doc": self.doc,
        }

    @classmethod
    def from_dtype(cls, dtype: np.dtype, doc: str = "") -> "OutputSchema":
        """从 NumPy dtype 创建 OutputSchema

        Args:
            dtype: NumPy 结构化 dtype
            doc: schema 说明

        Returns:
            OutputSchema 实例
        """
        if dtype.names is None:
            # 非结构化 dtype
            return cls(
                fields=(FieldSpec(name="value", dtype=str(dtype)),),
                dtype=str(dtype),
                kind="array",
                doc=doc,
            )

        fields = []
        dtype_fields = dtype.fields
        assert dtype_fields is not None  # guaranteed by dtype.names check above
        for name in dtype.names:
            field_dtype = dtype_fields[name][0]
            fields.append(
                FieldSpec(
                    name=name,
                    dtype=str(field_dtype),
                )
            )
        return cls(
            fields=tuple(fields),
            dtype=str(dtype),
            kind="structured_array",
            doc=doc,
        )


@export
@dataclass(frozen=True)
class InputRequirement:
    """输入依赖需求

    描述对某个依赖数据的具体需求。

    Attributes:
        name: 依赖的数据名称
        version_spec: 版本约束（PEP 440 格式，如 '>=1.0.0'）
        required_fields: 需要的字段列表
        doc: 需求说明
    """

    name: str
    version_spec: Optional[str] = None
    required_fields: Tuple[str, ...] = ()
    doc: str = ""


@export
@dataclass(frozen=True)
class Capabilities:
    """插件能力声明

    声明插件支持的执行模式和特性。

    Attributes:
        supports_streaming: 是否支持流式处理
        supports_parallel: 是否支持并行执行
        supports_gpu: 是否支持 GPU 加速
        idempotent: 是否幂等（相同输入总是产生相同输出）
        deterministic: 是否确定性（不依赖随机数）
        time_field: 时间字段名称（用于时序数据对齐）
    """

    supports_streaming: bool = False
    supports_parallel: bool = True
    supports_gpu: bool = False
    idempotent: bool = True
    deterministic: bool = True
    time_field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "supports_streaming": self.supports_streaming,
            "supports_parallel": self.supports_parallel,
            "supports_gpu": self.supports_gpu,
            "idempotent": self.idempotent,
            "deterministic": self.deterministic,
            "time_field": self.time_field,
        }


@export
@dataclass
class PluginSpec:
    """插件完整契约规范

    定义插件的机器可读契约，用于：
    - 注册时校验插件完整性和一致性
    - 自动生成文档
    - 计算 lineage hash 保证缓存一致性
    - 依赖解析和版本兼容性检查

    Attributes:
        name: 插件类名
        provides: 提供的数据名称
        version: 语义化版本号
        depends_on: 输入依赖列表
        output_schema: 输出数据 schema
        config_spec: 配置字段规范字典（键为配置名，值为 ConfigField）
        capabilities: 能力声明
        description: 插件描述
        deprecated: 弃用信息（如果已弃用）
        superseded_by: 替代插件名称（如果已弃用）

    Examples:
        >>> spec = PluginSpec(
        ...     name="BasicFeaturesPlugin",
        ...     provides="basic_features",
        ...     version="1.2.0",
        ...     depends_on=(InputRequirement("st_waveforms"),),
        ...     output_schema=OutputSchema.from_dtype(np.dtype([
        ...         ("amplitude", "f8"),
        ...         ("rise_time", "f8"),
        ...     ])),
        ...     config_spec={
        ...         "threshold_mv": ConfigField(type="float", default=10.0, doc="Threshold in mV"),
        ...         "baseline_samples": ConfigField(type="int", default=100, doc="Baseline samples"),
        ...     },
        ...     capabilities=Capabilities(supports_streaming=True),
        ... )
    """

    name: str
    provides: str
    version: str
    depends_on: Tuple[InputRequirement, ...] = ()
    output_schema: Optional[OutputSchema] = None
    config_spec: Dict[str, ConfigField] = field(default_factory=dict)
    capabilities: Capabilities = field(default_factory=Capabilities)
    description: str = ""
    deprecated: Optional[str] = None
    superseded_by: Optional[str] = None

    @property
    def config_keys(self) -> Tuple[str, ...]:
        """向后兼容：返回配置键列表"""
        return tuple(self.config_spec.keys())

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典（用于 lineage hash）"""
        return {
            "name": self.name,
            "provides": self.provides,
            "version": self.version,
            "depends_on": [
                {
                    "name": dep.name,
                    "version_spec": dep.version_spec,
                    "required_fields": list(dep.required_fields),
                }
                for dep in self.depends_on
            ],
            "output_schema": self.output_schema.to_dict() if self.output_schema else None,
            "config_spec": {
                key: cf.to_dict() for key, cf in self.config_spec.items()
            },
            "capabilities": self.capabilities.to_dict(),
            "description": self.description,
            "deprecated": self.deprecated,
            "superseded_by": self.superseded_by,
        }

    def validate(self) -> List[str]:
        """校验 spec 完整性

        Returns:
            错误信息列表，空列表表示校验通过
        """
        errors = []

        if not self.name:
            errors.append("name is required")
        if not self.provides:
            errors.append("provides is required")
        if not self.version:
            errors.append("version is required")

        # 校验版本格式
        try:
            from packaging.version import Version

            Version(self.version)
        except ImportError:
            pass  # packaging 不可用时跳过
        except Exception as e:
            errors.append(f"invalid version '{self.version}': {e}")

        return errors

    @classmethod
    def from_plugin(cls, plugin: Any) -> "PluginSpec":
        """从 Plugin 实例创建 PluginSpec

        自动提取插件的属性生成 spec。

        Args:
            plugin: Plugin 实例

        Returns:
            PluginSpec 实例
        """
        # 提取依赖
        depends_on = []
        for dep in plugin.depends_on:
            if isinstance(dep, tuple):
                depends_on.append(InputRequirement(name=dep[0], version_spec=dep[1]))
            else:
                depends_on.append(InputRequirement(name=dep))

        # 提取输出 schema
        output_schema = None
        if plugin.output_dtype is not None:
            try:
                dtype = np.dtype(plugin.output_dtype)
                output_schema = OutputSchema.from_dtype(dtype, doc=plugin.description)
            except Exception:
                pass

        # 提取能力
        capabilities = Capabilities(
            supports_streaming=getattr(plugin, "output_kind", "static") == "stream",
            supports_parallel=True,  # 默认支持
            idempotent=not getattr(plugin, "is_side_effect", False),
        )

        # 提取配置规范
        config_spec = {}
        for key, opt in plugin.options.items():
            config_spec[key] = ConfigField.from_option(opt)

        return cls(
            name=plugin.__class__.__name__,
            provides=plugin.provides,
            version=getattr(plugin, "version", "0.0.0"),
            depends_on=tuple(depends_on),
            output_schema=output_schema,
            config_spec=config_spec,
            capabilities=capabilities,
            description=getattr(plugin, "description", ""),
        )
