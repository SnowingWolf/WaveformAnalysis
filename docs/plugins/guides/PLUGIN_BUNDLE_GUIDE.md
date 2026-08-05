# 插件 Bundle 组织指南

**导航**: [文档中心](../../README.md) > [插件系统](../README.md) > 插件 Bundle

Plugin bundle 是一个正式插件产物的独立 Python 包。它把实现、机器可读元数据、公开导出、
依赖声明和定向测试放在同一目录中，使插件的代码属主、缓存版本和维护边界保持一致。

> 本文中的 plugin bundle 指插件源码目录，不是 `RecordsBundle`、`RecordsBundleRef` 等运行时
> 数据容器。后者只是多个正式产物复用计算或存储的内部实现。

## 核心规则

内置插件遵循一个 `provides` 对应一个 bundle：

```text
waveform_analysis/core/plugins/builtin/
├── records/              # provides: records
├── wave_pool/            # provides: wave_pool
├── hit_threshold/        # provides: hit_threshold
├── hit_merged/           # provides: hit_merged
├── peaklets/             # provides: peaklets
└── peaklet_channels/     # provides: peaklet_channels
```

一个 bundle 只拥有一个正式插件产物。具有相近功能、共享底层计算或处于同一 DAG 家族，
都不构成把多个 `provides` 合并到同一插件中的理由。

## 标准目录

```text
<provides>/
├── manifest.yaml
├── __init__.py
├── plugin.py
├── _compute.py           # 可选
├── requirements.txt
└── tests/
    └── test_<provides>.py
```

| 文件 | 职责 |
| --- | --- |
| `manifest.yaml` | 声明 `provides`、插件类、版本和依赖关系 |
| `plugin.py` | 插件类、配置解析以及与 Context 的交互 |
| `_compute.py` | 可选的纯计算、Numba kernel 或共享实现 |
| `__init__.py` | bundle 的稳定公开 Python API |
| `requirements.txt` | bundle 的第三方运行依赖 |
| `tests/` | 与该产物契约直接对应的定向测试 |

`plugin.py` 与 `_compute.py` 的拆分不是强制的。只有在计算逻辑需要独立测试、跨实现复用，
或需要把编排层与热点算法分开时才增加 `_compute.py`。

## Manifest 是插件属主声明

典型 manifest：

```yaml
provides: hit_threshold
plugin_class: ThresholdHitPlugin
version: 1.2.0
depends_on:
  - records
third_party_dependencies:
  - numpy
plugin_dependencies: []
category: feature_extraction
```

字段含义：

- `provides`：DAG 和 Context 使用的正式数据产物名，全局唯一。
- `plugin_class`：拥有该产物的插件类。
- `version`：插件行为版本，参与缓存 lineage。
- `depends_on`：正式数据依赖，不表示 Python import 关系。
- `third_party_dependencies`：NumPy、SciPy 等外部 Python 依赖。
- `plugin_dependencies`：跨 bundle 的实现复用关系。
- `category`：文档和发现层使用的分类。

注册表只扫描含 `manifest.yaml` 的目录，因此缺少 manifest 的 legacy 模块不属于正式 bundle。

## `__all__` 是公开导出真源

bundle 的 `__init__.py` 隔离内部文件布局，并明确允许外部使用的名称：

```python
from waveform_analysis.core.plugins.builtin.peaklets._compute import PEAKLET_DTYPE
from waveform_analysis.core.plugins.builtin.peaklets.plugin import PeakletPlugin

__all__ = ["PeakletPlugin", "PEAKLET_DTYPE"]
```

推荐从 bundle 根路径导入：

```python
from waveform_analysis.core.plugins.builtin.peaklets import (
    PEAKLET_DTYPE,
    PeakletPlugin,
)
```

外部代码不应依赖 `plugin.py`、`_compute.py` 或其他私有文件的位置。内部实现可以调整，
但 `__all__` 中名称的对象身份和语义属于公开兼容契约。

## Canonical Bundle 与兼容转发

部分历史家族入口仍会转发兄弟 bundle。例如 `builtin.hit` 可导出
`ThresholdHitPlugin`，但该插件的 canonical bundle 是 `builtin.hit_threshold`；
`builtin.peaks` 也会转发 peaklet 家族的类和 dtype。

判断属主时遵循：

1. `manifest.yaml` 中 `plugin_class` 所在 bundle 是插件类的 canonical owner。
2. leaf bundle 自己声明的 dtype、常量和 helper 由该 leaf bundle 所有。
3. 家族入口中的 re-export 只用于兼容，不转移代码属主、版本或测试责任。
4. `builtin.cpu`、`builtin` 和 `core.plugins` 是兼容 facade，不是新的插件 bundle。

新代码应优先使用 canonical bundle 路径。维护兼容入口时必须保证转发结果与 canonical
对象相同，不能复制类、dtype 或常量。

## 共享计算不合并产物

一个 `provides` 一个 bundle 不禁止共享实现。例如 `records` 与 `wave_pool` 可以复用
`records/_compute.py` 中的底层构建逻辑，但仍由两个插件分别提供正式产物：

```text
records/_compute.py       # 共享底层构建逻辑
records/plugin.py         # provides: records
wave_pool/plugin.py       # provides: wave_pool
```

共享必须满足：

- 算法属主唯一，兄弟 bundle 单向依赖属主实现。
- 每个正式产物保持独立的插件类、`provides`、version 和 lineage。
- 下游插件只依赖正式产物，不依赖内部 bundle、临时文件或私有 Context 状态。
- 修改共享实现时同时检查所有消费方的行为、缓存版本和测试。

## Bundle、Plugin Set 与 Profile

三者解决不同问题：

| 概念 | 作用 | 是否拥有插件实现 |
| --- | --- | --- |
| Bundle | 封装一个正式产物的实现与契约 | 是 |
| Plugin Set | 组合一个职责域需要的若干插件 | 否 |
| Profile | 组合多组插件形成可执行 pipeline | 否 |
| 兼容 facade | 保留旧导入路径并转发公开名称 | 否 |

插件属于哪个 bundle 不会因为它被加入某个 Plugin Set 或 Profile 而改变。

## 新增 Bundle 检查单

1. 创建 `builtin/<provides>/`，确保目录名与 `provides` 一致。
2. 在 `manifest.yaml` 声明唯一 `provides`、`plugin_class`、version 和依赖。
3. 在 `plugin.py` 实现单一职责的插件类。
4. 在 `__init__.py` 用显式 `__all__` 暴露稳定接口。
5. 仅在需要时增加 `_compute.py`，避免复制兄弟 bundle 的算法。
6. 在 bundle 自己的 `tests/` 中覆盖正常路径、空输入、边界输入和 dtype。
7. 按使用场景把插件加入适当的 Plugin Set；不要把注册逻辑放回兼容 facade。
8. 生成插件参考文档，并运行影响、schema、文档同步与锚点检查。

插件契约、依赖、配置、lineage 和生命周期的完整说明见
[插件系统与模板 API](../PLUGIN_SYSTEM_OVERVIEW.md)。
