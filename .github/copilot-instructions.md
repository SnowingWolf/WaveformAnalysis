# Copilot Instructions for WaveformAnalysis

- **项目基调**：`waveform_analysis` 是 DAQ 波形分析包，核心是插件化上下文 (`core/context.py` + `plugins.py`) 与链式的 `WaveformDataset` 封装 (`core/dataset.py`)；默认数据目录 `DAQ/<char>`，输出到 `outputs/`。
- **安装与环境**：优先 `./install.sh` 或 `pip install -e .`（开发依赖 `pip install -e ".[dev]"`）。Python ≥3.8，`pyproject.toml` 配置了 Black/pytest/mypy。
  - **本地环境**：指定 Python 路径 `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python` (Conda: `pyroot-kernel`)。需手动激活 Conda (`conda_first`) 后激活环境。
- **测试习惯**：运行 `pytest -v --cov=waveform_analysis --cov-report=html --cov-report=term`（pyproject 已内置 addopts）。
- **CLI 快速路径**：`waveform-process --char <run> --time-window 100 --verbose` 走完整流程并保存 CSV/Parquet；`--scan-daq/--show-daq` 通过 `utils.daq.DAQAnalyzer` 扫描/展示 DAQ 目录。
- **Dataset 链式流程**：典型链条 `load_raw_data() → extract_waveforms() → structure_waveforms() → build_waveform_features() → build_dataframe() → group_events(time_window_ns=100) → pair_events()`；所有方法用 `@chainable_step`，失败记录在 `_step_status/_step_errors`，`raise_on_error` 控制是否抛异常。
- **波形可选加载**：构造 `WaveformDataset(load_waveforms=False)` 可跳过原始波形提取与结构化（节省 70–80% 内存，无法调用 `get_waveform_at`），特征计算仍可用；示例见 `examples/skip_waveforms.py`。
- **时间戳索引**：`structure_waveforms` 后会为每通道构建 `_timestamp_index` 以加速 `get_waveform_at`；若手动修改 `st_waveforms`，需调用 `_build_timestamp_index()`。
- **特征扩展约定**：`register_feature(name, fn, **params)` 其中 `fn(self, st_waveforms, pair_len, **params) -> List[np.ndarray]`（每通道一组特征），再调用 `compute_registered_features()` 并在 `build_dataframe()` 时合并。
- **事件配对策略**：`group_events` 使用 `time_window_ns`（默认 100）窗口分组；`pair_events` 依赖 `pair_len` 和 channel 顺序，默认通道起始 `start_channel_slice=6` 对应 CH6/CH7。
- **缓存与签名**：步骤级缓存通过 `set_step_cache(step, enabled=True, attrs=[...], persist_path=..., watch_attrs=[...])`；持久化时写入 `WATCH_SIG_KEY="__watch_sig__"`（mtime/size SHA1），签名不匹配视为 cache miss。
- **插件式 Context**：`Context.get_data(run_id, name)` 会按 DAG 解析 `depends_on`，必须显式传 `run_id`；插件需声明 `provides/depends_on/options/version/dtype`，`compute` 返回 ndarray/generator，`is_side_effect` 输出隔离到 `_side_effects/{run_id}/{plugin}`。
- **存储策略**：默认 `MemmapStorage`（`core/storage.py`）零拷贝访问，原子写 `.tmp`→rename，校验 `dtype.descr`、`STORAGE_VERSION`；生成器被包装为 `OneTimeGenerator`，消费后若需重跑会重新构建。
- **血缘追踪**：`Context.key_for` 将插件名、版本、配置、dtype、依赖 lineage 哈希后作为缓存键；逻辑变化自动失效旧缓存，`lineage_visualizer` 在 `utils/visualization/lineage_visualizer.py`。
- **时间区间与 Chunk 操作**（`core/chunk_utils.py`）：
  - **Chunk 对象**：`Chunk(data, start, end, run_id, ...)` 封装了数据与时间边界，支持 `.split(t)`。
  - **endtime 计算**：`compute_endtime(data)` 由 `time + dt * length` 推导；`add_endtime_field()` 为数组添加字段；`validate_endtime()` 校验一致性。
  - **时间范围**：`get_time_range(data)` 返回 `(min_time, max_endtime)`；`select_time_range(data, start, end, strict=False)` 筛选有交集的记录；`clip_to_time_range()` 裁剪并调整 time/length。
  - **校验函数**：`check_monotonic(data, field, strict=False)` 检查单调性；`check_no_overlap(data)` 检查无重叠；`check_sorted_by_time()` 综合检查；`check_chunk_boundaries()` 检查跨界违规。
  - **Chunk 分割**：`split_by_time()` 按时间切分；`split_by_count()` 按记录数切分；`split_by_breaks()` 在大间隙处断开。
  - **重分块**：`rechunk()` 让 chunk 大小均匀；`rechunk_to_boundaries()` 对齐到指定边界。
  - **工具函数**：`sort_by_time()`、`concat_sorted()`、`merge_chunks()`。
  - **数据类**：`ChunkInfo`（start_time, end_time, n_records, chunk_i）、`ValidationResult`（is_valid, errors, warnings, stats）。
- **DAQ 集成**：`WaveformDataset.check_daq_status()` 可通过 `daq_report` JSON 或 `DAQAnalyzer` 获取通道列表与文件；CLI `--scan-daq` 生成报告。
- **示例定位**：快速参考 `examples/basic_analysis.py`（全流程）、`examples/advanced_features.py`（特征/链式扩展）、`examples/skip_waveforms.py`（内存优化）。
- **文档索引**：`docs/ARCHITECTURE.md`（整体架构与数据流）、`docs/CACHE.md`（Lineage/memmap 签名策略）、`docs/MEMORY_OPTIMIZATION.md`（load_waveforms=False 行为）、`docs/PROJECT_STRUCTURE.md`（目录/入口）。
- **常见陷阱**：
  - 生成器输出只能消费一次；重复读取会触发重算。
  - 缺少 `run_id` 会导致 Context 数据覆盖或血缘冲突。
  - 变更 dtype/version/options 后务必 bump `version` 或依赖 `dtype.descr`，否则 lineage 不一致会强制重算。
  - 数据默认找 `DAQ/<char>`；缺失文件会在 `load_raw_data` 抛 `FileNotFoundError`（测试环境可 `pytest.skip`）。
  - **Chunk 边界**：记录的 endtime 不应超过 chunk 边界，否则 `check_chunk_boundaries()` 报错。
- **模块导出管理**（`core/utils.py: exporter()`）：
  - **强制规范**：所有新模块必须使用 `from waveform_analysis.core.utils import exporter` 管理导出。
  - **标准模板**：
    ```python
    from waveform_analysis.core.utils import exporter
    export, __all__ = exporter()

    @export
    class MyClass: ...

    @export(name="AlternativeName")
    def my_func(): ...

    # 导出常量
    MY_CONST = export(42, name="MY_CONST")
    ```
  - 禁止手动维护 `__all__ = [...]` 列表。
- **数据处理哲学**：
  - 效仿 `strax`，优先使用 `Chunk` 对象封装 `(data, start, end)`。
  - 核心逻辑（如 `split`, `merge`）应作为 `Chunk` 的方法或 `chunk_utils` 中的导出函数。
- **贡献提示**：保持公共 API 兼容（`__init__.py` 导出），新增命令行参数记得在 `cli.py` epilog 示例补充；文档在 `docs/`，更新功能优先补 `ARCHITECTURE`/`USAGE` 对应章节。
