# 🧩 插件编写规范

**导航**: [文档中心](../README.md) > [plugins](README.md) > 插件编写规范

面向开发者的插件编写规范与最佳实践，覆盖目录、声明、配置、缓存、性能与测试。

---

## ✅ 适合谁

- 计划新增或改造插件（CPU / Streaming / Adapter）
- 需要确保插件符合 DAG、缓存、dtype 和配置约定

---

## 1) 基本原则

- **一插件一职责**：单一输入 → 单一产物，不做额外副作用。
- **稳定输出**：`dtype`、字段语义、单位保持一致；变更必须 bump `version`。
- **显式依赖**：只依赖 `depends_on` 声明的数据，避免隐式状态或全局缓存。
- **可重复性**：同一 `run_id` + config 结果可重复。

---

## 2) 目录与导入

### 插件放置位置

- CPU 插件：`waveform_analysis/core/plugins/builtin/cpu/`
- Streaming 插件：`waveform_analysis/core/plugins/builtin/streaming/`
- Legacy 兼容：`waveform_analysis/core/plugins/builtin/legacy/`（不建议新增）

### 推荐导入方式

```python
from waveform_analysis.core.plugins.builtin.cpu import MyPlugin
```

---

## 3) 插件元数据（必须）

每个插件必须声明以下属性：

- `provides`: 输出数据名（全局唯一）
- `depends_on`: 上游数据列表（DAG 依赖）
- `options`: 可配置项与默认值
- `version`: 整数，行为或输出变化必须递增
- `dtype`: 输出结构化数组 dtype

---

## 4) 配置与 Context

- 插件不要维护全局状态；所有配置通过 `Context` 传入。
- 推荐使用插件特定配置：

```python
ctx.set_config({"threshold": 50}, plugin_name="signal_peaks")
```

- 如需跨插件一致配置（如 `daq_adapter`），使用全局配置：

```python
ctx.set_config({"daq_adapter": "vx2730"})
```

---

## 5) 输出与 dtype 规范

- 字段命名使用业务术语：`time`, `dt`, `length`, `event_length`。
- 时间字段单位需一致（ps/ns 等）并在 docstring 中明确。
- 多通道结构化输出应返回单个 `np.ndarray`，通过 `channel` 字段区分通道。
- 仅在没有 `channel` 字段且必须保持分通道输出时使用 `List[np.ndarray]`（旧格式）。
- 如输出是 DataFrame，字段名稳定，避免动态拼接。

---

## 6) 版本与缓存

### 必须 bump `version` 的场景

- 输出 `dtype` 变化（字段、类型、顺序）
- 计算逻辑变化导致数值语义变化
- 默认配置更改影响结果

### 缓存一致性

- 不依赖外部环境随机性（或固定种子）。
- 如依赖文件变更，确保能被 watch signature 捕获。

---

## 7) Streaming 插件规则

- 仅当数据天然适合 chunk 处理时使用 streaming。
- chunk 必须满足边界约束：`endtime <= chunk end`。
- 明确 `time_field` 与 `break_threshold_ps` 语义。
- 不允许跨 chunk 共享隐式状态（可将状态显式放入缓存）。

---

## 8) 性能与并行

- 优先 NumPy 向量化，避免 Python for 循环。
- 热点路径可用 Numba（遵循现有用法）。
- 需要并行时优先使用 `ExecutorManager` 的配置：
  - `io_intensive`, `cpu_intensive`, `large_data`, `small_data`

---

## 9) 错误处理

- 输入不符合预期必须抛出明确异常（包含 `run_id` / `data_name`）。
- 不要吞错；错误应由 Context 或调用方处理。

---

## 10) 最小模板

```python
from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.plugin import Plugin
import numpy as np

export, __all__ = exporter()


@export
class MyPlugin(Plugin):
    provides = "my_data"
    depends_on = ("st_waveforms",)
    options = dict(threshold=50)
    version = 1
    dtype = np.dtype([("time", "int64"), ("value", "f4")])

    def compute(self, st_waveforms, **kwargs):
        threshold = self.config.get("threshold", 50)
        # ... compute ...
        return np.zeros(0, dtype=self.dtype)
```

---

## 11) 测试建议

- 新插件至少覆盖：
  - 基本执行（能在 DAG 中生成输出）
  - dtype 与字段稳定
  - 配置项生效（默认值与自定义值）
  - 缓存命中一致性（同 config 结果一致）

---

## 12) 常见坑

- 忘记显式 `run_id` 触发缓存冲突
- 输出 dtype 改动未 bump `version`
- 在插件内缓存状态导致跨 run 污染
- chunk 边界未验证导致时间范围错误
