# 测试去过时化与文档自动生成系统联动改进计划

**导航**: [文档中心](../README.md) > [更新记录](README.md) > 测试与文档联动改进计划

## 1. 背景与目标

当前测试目录存在重复与过时测试资产，且文档自动生成/同步校验虽已具备工具链，但未与本次测试治理形成统一执行闭环。

本计划目标：
- 清理重复、过时、误导性测试资产，降低维护成本；
- 将插件文档自动生成与文档同步校验并入改动流程；
- 确保发布前门禁（含文档和关键测试）与仓库现状一致。

---

## 2. 范围与策略

### 2.1 测试侧（本次执行）

- 删除完全重复测试文件（保留一份语义清晰且路径稳定的版本）；
- 删除 `test_*.py` 但不被 pytest 发现为测试用例的文件；
- 删除历史演示脚本（命名为 `test_*.py` 但不属于自动化测试链路）；
- 删除与当前实现行为失配且确认不再维护的过时测试用例。

### 2.2 文档侧（新增纳入）

将文档自动生成与校验加入本次改进后的固定流程：

1) 生成插件参考文档（auto + agent）
```bash
waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
```

2) 文档同步与锚点校验
```bash
bash scripts/check_doc_sync.sh HEAD
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

3) 发布前统一校验
```bash
python scripts/release_artifact_sync.py --base HEAD
```

---

## 3. 详细执行步骤

### 步骤 A：测试资产去过时化

- 删除重复测试文件：
  - `tests/test_cache_utils.py`
  - `tests/test_processor.py`
- 保留对应主文件：
  - `tests/test_cache.py`
  - `tests/test_event_grouping.py`
- 在 `tests/test_event_grouping.py` 删除已失配的过时用例：
  - `test_structure_waveforms`
- 删除 0 用例文件：
  - `tests/test_simple_batch.py`
- 删除根目录历史演示脚本：
  - `test_progress_fix.py`
  - `test_progress_simple.py`

### 步骤 B：文档自动生成并回填

- 执行 `waveform-docs generate plugins-auto ...`
- 执行 `waveform-docs generate plugins-agent ...`
- 检查生成目录是否有意外缺失或新增（尤其 `INDEX.md` 与单插件页）。

### 步骤 C：文档同步与发布闸门修正

- 执行 `check_doc_sync` 和 `check_doc_anchors`；
- 检查 `scripts/release_artifact_sync.py` 中关键测试路径是否仍引用已删除用例；
- 若引用过时文件，替换为当前等价且稳定的测试入口，保证门禁可持续通过。

### 步骤 D：验证与记录

- 执行测试收集验证与定向回归；
- 记录命令与 PASS/FAIL 摘要，写入 PR 描述。

---

## 4. 验收标准

### 4.1 测试验收

- `pytest --collect-only` 中不再出现重复收集的重复文件组；
- 不再存在 `test_*.py` 但 0 用例的测试文件；
- 定向回归测试通过（至少覆盖保留后的核心文件）。

### 4.2 文档验收

- auto/agent 文档生成命令成功；
- `check_doc_sync`、`check_doc_anchors` 全通过；
- 生成目录与仓库内容一致，无明显漏页或脏变更。

### 4.3 门禁验收

- `release_artifact_sync.py` 全流程通过；
- 不再引用已删除测试文件或过时路径。

---

## 5. 风险与应对

- 风险：删除测试后覆盖率下降。
  应对：仅删重复/过时项，保留等价覆盖主文件；必要时补充更贴近当前行为的新用例。

- 风险：文档生成产物与现有手工文档风格差异。
  应对：以自动生成目录为准，人工文档仅保留导航与解释，不复制插件细节。

- 风险：发布门禁脚本仍依赖历史文件。
  应对：本计划内同步修正脚本引用，并纳入后续 code review 检查项。

---

## 6. PR 记录模板（建议）

在 PR 描述中附上：

- 测试清理摘要（删除/保留清单）；
- 文档命令执行结果：
  - `waveform-docs generate plugins-auto ...`：PASS/FAIL
  - `waveform-docs generate plugins-agent ...`：PASS/FAIL
  - `bash scripts/check_doc_sync.sh HEAD`：PASS/FAIL
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`：PASS/FAIL
  - `python scripts/release_artifact_sync.py --base HEAD`：PASS/FAIL
- 备注：若存在失败项，说明原因与后续处理计划。
