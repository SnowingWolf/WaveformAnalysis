# waveform-docs 命令参考

**导航**: [文档中心](../README.md) > [命令行工具](README.md) > waveform-docs 命令参考

`waveform-docs` 是 WaveformAnalysis 的文档生成工具，用于自动生成插件文档、构建 Next 静态总站、检查 Markdown 链接和文档覆盖率。
文档工具要求 Python 3.10 或更高版本；仓库同时安装多个解释器时，可通过
`WAVEFORM_PYTHON=/path/to/python` 选择解释器（Makefile 和文档同步脚本会沿用该选择）。

---

## 命令概述

`waveform-docs` 提供以下功能：
- 自动生成内置插件文档
- 生成完全离线的 Next HTML 文档总站，并在本机预览
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

检查文档链接或插件覆盖率。

```bash
waveform-docs check links [选项]
waveform-docs check coverage [选项]
```

`check links` 离线扫描 `docs/` 下的 Markdown，检查相对文件链接、图片等本地资源，以及同页和跨页
fragment。HTTP(S)、`mailto:` 等外部链接不会被网络请求；链接错误返回退出码 `1`。

### serve - 本地预览

只服务已存在的静态站点目录，不生成站点，也不打开浏览器。

```bash
waveform-docs serve --directory docs/_site --host 127.0.0.1 --port 8000
```

如需让全局 DAG 读取一个已配置的运行时 `Context`，可传入一个可信的无参工厂：

```bash
waveform-docs serve \
  --directory docs/_site \
  --host 0.0.0.0 \
  --lineage-context-factory my_project.docs:create_context
```

此时浏览器访问 `?lineage=live` 会从同源 `GET /api/lineage` 读取当前插件与配置解析出的
端口级 DAG。接口只返回拓扑和文档元数据，不接受 `run_id`、不读取运行数据，也不会执行插件。
未提供工厂、接口不可用或请求失败时，页面自动使用生成时写入的静态 DAG。

---

## 文档类型

| 类型 | 说明 | 默认输出 |
|------|------|----------|
| `plugins-auto` | 自动生成内置插件文档 | `docs/plugins/reference/builtin/auto/` |
| `plugins-agent` | 生成 agent 导向插件文档 | `docs/plugins/reference/agent/` |
| `site-web` | 生成包含插件、Context、Accessor 与可视化参考的离线 HTML 文档总站 | `docs/_site/` |

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

`--docs-dir` 同时适用于 `check links` 和 `check coverage`。质量门禁统一使用退出码：`0` 表示通过或
默认容忍的 warning，`1` 表示错误，`2` 表示在传入 `--fail-on-warning` 后仍存在 warning。
传入该选项可明确表达“警告也不能被忽略”的 CI 意图。

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

# 生成包含插件、Context、Accessor 与可视化参考的 HTML 文档总站
waveform-docs generate site-web

# 检查 docs/ 下的 Markdown 本地链接、资源和 fragment
waveform-docs check links --docs-dir docs
```

`site-web` 生成总站首页，并将插件、Context、Accessor 和可视化参考交给 `docs/site-next/` 的
Next 应用导出。总站只支持全量生成，因此不能与 `--plugin` 同时使用；`plugins-auto` 和
`plugins-agent` 仍负责 Markdown 文档生成。

源码 checkout 必须先在 `docs/site-next/` 安装 Node 依赖（例如运行 `npm ci`）。`site-web`
不会自动联网或安装依赖；缺少 `node_modules/` 时会给出可执行的安装提示。构建时 Python
先生成临时 `site-model/v1` JSON（路径通过 `WAVEFORM_DOCS_SITE_MODEL` 传入 Next），再运行
`npm run check` 和 `npm run build`。安装后的 wheel 不依赖 Node，而是校验并复制随包提供的
预构建导出和 `site-manifest.json` 哈希清单；没有有效预构建产物时命令失败，不回退到模板。

`site-web` 会先在输出目录旁生成并校验完整站点，再整体替换目标目录。生成或本地链接校验失败时，
原站点保持不变；成功发布会移除上一轮遗留文件。因此 `docs/_site` 应仅存放生成产物，不应放置
需要保留的手工文件。运行中的 `waveform-docs serve` 无需重启，后续请求会读取新发布的文件。
该服务对 HTML、JSON、脚本和样式统一发送禁缓存响应头，避免浏览器或转发层继续复用旧页面。

发布前校验还会检查 HTML `href`/`src` 对应文件和 fragment、搜索索引中的每个 URL，以及每个
`aria-controls` 是否指向当前页面存在的 DOM 节点。任一项失败都会阻断原子发布并保留旧站点。

`site-web` 还会读取 `docs/site-guides.yaml`，把显式收录的 Markdown 标题、段落、代码和表格事实
写入 `site-model/v1`，由 Next 应用负责展示。Markdown 文件是正文唯一真源；Python builder
不创建 HTML，也不加载 Jinja web 模板。

清单使用 `schema_version: 2`，每个分类声明 `id`、`title` 与 `index_route`；`source_dirs` 目录扫描
自动收录 Markdown，也可用显式 `pages` 声明个别页面：

```yaml
schema_version: 2
sections:
  - id: architecture
    title: 系统架构与数据模型
    index_route: /architecture/
    source_dirs:
      - docs/architecture
    pages:
      - source: docs/architecture/ARCHITECTURE.md
        route: /architecture/system/
```

`source` 必须是 `docs/` 内存在的 Markdown 文件。`index_route` 与 `route` 必须使用带首尾斜杠的
extensionless canonical URL；`.html`、fragment、query、路径逃逸、重复 source、重复 route、缺失资源
或与总站已有页面冲突都会阻断生成。旧 URL 只记录在 `docs/site-route-migration.yaml`，构建不会生成
redirect。页面导航和插件参考同样只使用 canonical route；仓库内未收录的 Markdown 链接仍由
`check links` 报告。

Next 应用负责顶部导航、文档树、全文搜索和 lineage 交互；Python builder 只提供真实插件、
Context、Accessor、可视化、guide 和 lineage facts。站点使用静态导出所需的本地资源，发布前
会检查所有模型 route、HTML 本地链接、fragment 和路径边界。需要预览时请使用
`waveform-docs serve`，不要把导出的 `index.html` 当作无服务器协议使用。

默认 lineage 来自真实插件注册表和解析后的依赖关系；`serve --lineage-context-factory` 才会
按请求创建 Context 并返回动态拓扑。该接口只返回端口、dtype、版本和依赖等元数据，不读取
run data，也不执行插件 compute。

### 2. 检查文档覆盖率

```bash
# 基本检查
waveform-docs check coverage

# 严格模式（检查 spec、生成内容、源码 fingerprint 与 Auto/Agent 漂移）
waveform-docs check coverage --strict

# 有警告时失败（退出码 2）
waveform-docs check coverage --fail-on-warning
```

覆盖率以插件文档 frontmatter 的真实 `provides` 为准，而不是以文件名猜测身份。普通检查会报告缺失、
版本过期、多余页面、frontmatter `provides` 与文件名不一致，以及重复声明；严格检查还会比较当前
代码事实与两套生成页面，拒绝动态依赖解析漂移、空的工作流/行为/失败模式/示例、无来源 fingerprint、
失效的 published AgentDoc 和占位说明。生成器在提取失败或插件实例化失败时会直接报错，不再静默跳过。

---

## 输出文件说明

### 插件文档

每个插件生成一个 Markdown 文件，包含：
- 基本信息（类名、版本、provides、声明依赖与默认画像下的解析依赖）
- 输出容器、执行模式、保存策略、`run_id`/运行配置契约
- 配置选项表（默认值、单位、范围/choices、弃用信息）
- 输出 schema（dtype 字段、单位和字段含义）
- 源码/AgentDoc 叙述来源与 `source_fingerprint`
- 基于当前插件 profile 的可运行使用示例、工作流和失败模式

生成的文件位于 `docs/plugins/reference/builtin/auto/` 目录：
- `raw_files.md`
- `st_waveforms.md`
- `records.md`
- `hit_threshold.md`
- `peaklets.md`
- `peaks.md`
- `events.md`
- `INDEX.md`（索引页）
- ...

Agent 导向文档默认位于 `docs/plugins/reference/agent/`：
- `INDEX.md`（agent 索引页）
- `<provides>.md`（每个插件一页）

`site-web` 使用 `docs/_site/` 作为派生产物目录，导出 `index.html`、extensionless route 对应的
`index.html` 页面、Next 静态资源和 `site-model.v1.json`。导出不得引用 CDN 或外部资源，可通过
`waveform-docs serve --directory docs/_site` 预览；该目录不会提交到仓库。历史 `.html` route
与新 route 的完整迁移表见 [`docs/site-route-migration.yaml`](../site-route-migration.yaml)。

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

`site-web` 的 Python builder 只读取 Markdown 事实，不渲染 HTML；Next 的依赖和静态导出工具
由 `docs/site-next/package.json` 管理。源码 checkout 需先执行 `npm ci`，而 wheel 路径只复制
随包预构建产物，不要求 Node。插件 Markdown 生成仍使用 `docgen` extra。

---

## 错误处理

### 常见错误

1. **缺少依赖**
   ```
   ❌ Next dependencies are not installed at .../docs/site-next/node_modules
   提示: 在 docs/site-next 运行 `npm ci`
   ```
   解决: 安装 Node 依赖后重新运行 `waveform-docs generate site-web`。

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
   - `site-web` 默认输出到 `docs/_site/`
   均会覆盖已有文件
3. **INDEX.md**: 自动生成索引页，包含所有插件的概览表

---

**相关文档**:
[CLI 工具总览](README.md) |
[插件开发指南](../plugins/README.md)
