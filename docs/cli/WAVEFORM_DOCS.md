# waveform-docs 命令参考

**导航**: [文档中心](../README.md) > [命令行工具](README.md) > waveform-docs 命令参考

`waveform-docs` 是 WaveformAnalysis 的文档生成工具，用于自动生成插件文档和检查文档覆盖率。

---

## 命令概述

`waveform-docs` 提供以下功能：
- 自动生成内置插件文档
- 生成完全离线的 HTML 文档总站或兼容的独立插件站点，并在本机预览
- 检查文档覆盖率

---

## 基本用法

```bash
waveform-docs <命令> [选项]
```

---

## 子命令

### generate - 生成文档

生成指定类型的文档。

```bash
waveform-docs generate <文档类型> [选项]
```

### check - 检查文档

检查文档覆盖率。

```bash
waveform-docs check coverage [选项]
```

### serve - 本地预览

只服务已存在的静态站点目录，不生成站点，也不打开浏览器。

```bash
waveform-docs serve --directory docs/_site --host 127.0.0.1 --port 8000
```

---

## 文档类型

| 类型 | 说明 | 默认输出 |
|------|------|----------|
| `plugins-auto` | 自动生成内置插件文档 | `docs/plugins/reference/builtin/auto/` |
| `plugins-agent` | 生成 agent 导向插件文档 | `docs/plugins/reference/agent/` |
| `plugins-web` | 生成离线插件 HTML 站点 | `docs/_site/` |
| `site-web` | 生成包含插件与 Accessor 的离线 HTML 文档总站 | `docs/_site/` |

---

## 选项

### generate 选项

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--output` | `-o` | str | - | 输出路径（目录） |
| `--plugin` | `-p` | str | - | 生成单个插件文档 |

### check 选项

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--docs-dir` | `-d` | str | - | 文档目录路径 |
| `--strict` | - | flag | False | 严格模式（也检查 spec 质量） |
| `--fail-on-warning` | - | flag | False | 有警告时也失败 |

---

## 使用示例

### 1. 生成内置插件文档

```bash
# 生成所有内置插件文档
waveform-docs generate plugins-auto

# 指定输出目录
waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/

# 生成单个插件文档
waveform-docs generate plugins-auto --plugin raw_files

# 生成所有 agent 插件文档
waveform-docs generate plugins-agent

# 指定输出目录
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/

# 生成单个插件文档
waveform-docs generate plugins-agent --plugin raw_files

# 生成离线 HTML 站点
waveform-docs generate plugins-web -o docs/_site

# 生成包含插件与 Accessor 的 HTML 文档总站
waveform-docs generate site-web
```

`site-web` 生成总站首页，并将插件站放在 `plugins/`、Accessor 参考放在 `accessors/`。
总站只支持全量生成，因此不能与 `--plugin` 同时使用。`plugins-web` 继续保留原有参数、默认输出和
文件布局，适合只需要插件参考或依赖旧路径的调用。

站点使用本地 MDN 风格的文档外壳：顶部导航、左侧文档树、详情页右侧章节目录，以及窄屏下可
展开的目录抽屉。所有页面均可打开全站搜索；生成器把插件、Accessor 和主要章节写入本地
`assets/search-index.js`，因此通过 `file://` 直接打开时也不依赖 `fetch`、CDN 或在线服务。
插件索引原有的页面内筛选仍保留，用于快速过滤当前卡片集合。

生成后的 HTML 首页使用本地 Plotly 提供可点击、可缩放、可拖拽的紧凑全局插件总览。`Core` 是
默认视图，保留以 `events` 为主终点的处理链；`All outputs` 额外显示 `df_paired`、
`waveform_width_integral` 等默认配置下无消费者的终点输出。两个视图从同一次完整图布局派生，
共享核心节点坐标；终点输出位于其生产者下方的疏松轨道。点击插件会在首页右侧打开
只包含该插件、直接输入和直接消费者的端口级 Plotly 谱系图，端口图复用运行时 Context 的渲染器，
并提供到完整插件参考页的链接。全局依赖使用弧形箭头以区分并行连接；`?focus=<provides>` 可直接
恢复该选择，`?view=core|all&focus=<provides>` 可分享完整页面状态。聚焦终点输出会自动切换到
`all`，视图切换、聚焦以及浏览器前进/后退会保持 URL 同步。下方卡片按正式 `PLUGIN_SETS` 的
执行顺序分组，搜索会隐藏无匹配的整个集合；`cache_analysis` 不属于处理 DAG，单独列在
`Standalone Tools`。

动态依赖使用独立的文档 profile 解析：共享值为 `wave_source=records`、`use_filtered=false`、
`daq_adapter=vx2730`，`hit_threshold.asymmetry_cut_enabled=true` 为插件专属值。优先级依次为插件
专属值、共享 profile、`Option.default`，因此 `hit_threshold` 在静态文档图中精确依赖 `records`、
`wave_pool`、`records_asymmetry_mask`。解析只调用 `resolve_depends_on()`，不读取 run data、缓存或
执行插件 compute。每个插件页仍包含直接上游和下游的局部 SVG 图，并可跳转到首页
对应插件的全局定位视图。站点包含本地 `plotly.min.js` 和 `lineage-details.json`，不引用 CDN 或外部
资源。Core/All 数据另存为 `lineage-overviews.json`，同时嵌入首页，直接通过 `file://` 打开时无需
fetch。图中 `Docs` 表示可用文档字段的加权完整度，`Impact` 表示该插件在默认解析图中的相对下游
覆盖范围；两者均为静态文档指标，不表示运行时性能、数据质量或缓存 lineage。

### 2. 检查文档覆盖率

```bash
# 基本检查
waveform-docs check coverage

# 严格模式（检查 spec 质量）
waveform-docs check coverage --strict

# 有警告时失败
waveform-docs check coverage --fail-on-warning
```

---

## 输出文件说明

### 插件文档

每个插件生成一个 Markdown 文件，包含：
- 基本信息（类名、版本、provides、依赖）
- 描述
- 输出 schema（dtype 字段）
- 配置选项表
- 使用示例

生成的文件位于 `docs/plugins/reference/builtin/auto/` 目录：
- `raw_files.md`
- `waveforms.md`
- `st_waveforms.md`
- `filtered_waveforms.md`
- `signal_peaks.md`
- `INDEX.md`（索引页）
- ...

Agent 导向文档默认位于 `docs/plugins/reference/agent/`：
- `INDEX.md`（agent 索引页）
- `<provides>.md`（每个插件一页）

`plugins-web` 站点位于 `docs/_site/`，包含 `index.html`、`plugins/<provides>.html` 与
本地 `assets/site.css` / `assets/site.js`。`site-web` 使用同一输出根目录，生成
`index.html`、`plugins/index.html`、`plugins/<provides>.html`、`accessors/index.html`、
两个 Accessor 详情页以及共享的 `assets/`。两种模式都不引用 CDN 或外部资源，可直接打开
`index.html`，也可通过 `waveform-docs serve --directory docs/_site` 预览。该目录属于派生产物，
不会提交到仓库。

---

## 依赖要求

Markdown 和插件文档生成需要以下依赖：

```bash
pip install jinja2
```

或者安装开发依赖：

```bash
pip install -e ".[docgen]"
```

`site-web` 的 Accessor Python 示例使用本地 Pygments 生成语法高亮；该依赖包含在
`docgen` extra 中，不作为 WaveformAnalysis 的主运行时依赖。生成 Accessor 页面时若缺少
Pygments，命令会明确提示安装 `.[docgen]`。

---

## 错误处理

### 常见错误

1. **缺少依赖**
   ```
   ❌ 缺少依赖: No module named 'jinja2'
   提示: 运行 'pip install jinja2' 安装依赖
   ```
   解决: 安装 `jinja2` 包

2. **插件不存在**
   ```
   ❌ 错误: Plugin 'xxx' not found
   ```
   解决: 检查插件名称是否正确

---

## 使用场景

### 场景 1: 更新插件文档

在插件代码更新后，重新生成文档：

```bash
waveform-docs generate plugins-auto
waveform-docs generate plugins-agent
```

### 场景 2: CI/CD 集成

在 CI 中检查文档覆盖率：

```bash
waveform-docs check coverage --strict --fail-on-warning
```

---

## 注意事项

1. **文档准确性**: 生成的文档基于插件的 `SPEC` 和 `options`，确保插件定义完整
2. **输出路径**:
   - `plugins-auto` 默认输出到 `docs/plugins/reference/builtin/auto/`
   - `plugins-agent` 默认输出到 `docs/plugins/reference/agent/`
   - `plugins-web` 与 `site-web` 默认输出到 `docs/_site/`
   均会覆盖已有文件
3. **INDEX.md**: 自动生成索引页，包含所有插件的概览表

---

**相关文档**:
[CLI 工具总览](README.md) |
[API 参考](../api/README.md) |
[插件开发指南](../plugins/README.md)
