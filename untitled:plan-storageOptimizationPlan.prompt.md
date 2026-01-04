# 存储层优化计划（storageOptimizationPlan）

**TL;DR:** 针对 `MemmapStorage` 的锁与写入健壮性、`save_stream` 的异常清理，以及 `tests/test_storage.py` 的类型/lint 问题，逐步添加单元测试与小改动以降低并发/损坏风险并提高 CI 稳定性。优先级从低到高：修复测试/类型 → 增加失败清理测试 → 加强锁逻辑 → 改善存在性检测与元数据持久性。

---

## 步骤（优先级与实现概要）

1. 修复并完善测试（低风险，快速见效）
   - 修改 `tests/test_storage.py`：
     - 修复未使用 import（例如移除或使用之）。
     - 在访问 `get_metadata` 返回值之前断言非 None（消除 mypy 警告）。
   - 目标：通过 linter/mypy 并提升类型安全性。

2. 添加关键单元测试（高价值）
   - `test_save_stream_cleanup_on_error`: 生成一个会在中途抛异常的 chunk（例如 yield 一个无法转换为 ndarray 的对象），断言：
     - `.tmp` 文件被清理（不存在），
     - `.lock` 文件被删除（不存在），
     - 异常被正确向上抛出。
   - `test_acquire_removes_stale_lock`: 创建一个过期的 lock 文件（写入老 timestamp），调用 `_acquire_lock` 并断言它能删除旧锁并成功获取锁（或返回 True）。
   - `test_exists_false_on_corruption`: 写入不匹配的元数据或损坏的二进制文件，断言 `exists()` 返回 False（或明确文档化当前语义）。

3. 强化锁实现（中风险）
   - 在 `MemmapStorage._acquire_lock` 增加 PID 存活检查（POSIX: `os.kill(pid, 0)`），仅当 PID 不存活且 lock 超时时才移除锁。
   - 可选：在支持的平台上优先使用 `fcntl` advisory lock（需处理跨平台兼容性）。
   - 为这部分写单元测试（模拟 `os.kill` 或 mock 出存活/死亡情境）。

4. 增强写入/持久化鲁棒性（中等风险）
   - 确保 `save_stream` 在异常路径上清理 `.tmp` 并总是释放 `.lock`（目前已有 finally，但添加测试验证）。
   - 在写入元数据时，采用 `tmp`→`rename` 的原子流程（当前已实现），并在需要时增加可选 `fsync` 以提高持久性（配置开关以兼顾性能）。

5. 文档与 CI（低成本）
   - 在 `docs/CACHE.md` 或 `docs/PROJECT_SUMMARY.md` 中补充关于锁的工作方式、限制（单机、时钟漂移、PID 重用）与推荐使用场景。
   - 在 CI 中增加 `flake8`/`mypy` 的检查与新增测试的运行，确保回归被及时捕获。

---

## 测试与验证建议（一行测试建议）
- 修复类型：在测试里 `assert meta is not None` 之后再读 `meta["storage_version"]`。
- 保存失败：用一个异常生成器调用 `save_stream` 并断言 `.tmp` 和 `.lock` 文件都不存在。
- 过期锁：创建 lock 文件写入老 timestamp，确认 `_acquire_lock` 能移除旧锁并获得新锁。
- exists() 语义：制造元数据/二进制不匹配，断言 `exists()` 返回 False（并记录语义到 docs）。

---

## 风险与取舍说明
- PID 存活检查在 POSIX 上可行，但需在 Windows 上退回到原有逻辑或使用 `fcntl`（Windows 不支持），因此需明确兼容策略。
- 引入 `fsync` 会提高持久性但损耗性能，需作为可选配置。

---

## 下步行动（选择一项）
1. 我先修测试与类型（低风险，能立刻在 CI 上看到效果）。
2. 我先写 `save_stream` 异常清理的单元测试与补丁（高价值验证）。
3. 我实现并测试改进的锁策略（需要讨论并确保跨平台安全）。

请选择优先项，随后我会生成具体补丁草案（含测试）以供本地运行与 review。