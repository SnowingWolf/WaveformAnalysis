

---

## 🎯 主要功能亮点

###  时间范围查询优化
- ⚡ **O(log n)** 查询复杂度（二分查找）
- 🔍 支持时间点和范围查询
- 💾 查询结果缓存
- 📊 索引统计和管理

###  Strax插件适配器
- 🔌 无缝集成strax插件
- 🔄 自动元数据提取
- 🎨 strax风格API支持
- ⚙️ 智能参数映射

###  多运行批量处理
- 🚀 并行处理支持
- 📈 进度跟踪
- 🛡️ 灵活的错误处理
- 🎛️ 自定义处理函数

###  数据导出统一接口
- 📦 6种格式支持（Parquet, HDF5, CSV, JSON, NPY, NPZ）
- 🔄 自动格式推断
- 💪 智能类型转换
- ⚡ 批量导出

###  插件热重载
- 🔥 文件变化自动监控
- ⚡ 即时重载
- 🧹 缓存自动清理
- 👨‍💻 开发友好

---

##  文档目录
### 核心模块
1. `waveform_analysis/core/time_range_query.py` - 时间范围查询优化
2. `waveform_analysis/core/strax_adapter.py` - Strax插件适配器
3. `waveform_analysis/core/data/batch_processor.py` / `export.py` - 批量处理与数据导出
4. `waveform_analysis/core/hot_reload.py` - 插件热重载

### 测试文件
5. `tests/test_time_range_query.py` - 时间范围查询测试
6. `tests/test_strax_adapter.py` - Strax适配器测试


---

## ⚡ 快速上手

### 1. 时间范围查询
```python
from waveform_analysis.core.context import Context

ctx = Context()
# 查询时间范围
data = ctx.time_range('run_001', 'st_waveforms',
                      start_time=1000, end_time=2000)
```

### 2. Strax插件集成
```python
from waveform_analysis.core.strax_adapter import wrap_strax_plugin

# 包装strax插件
adapter = wrap_strax_plugin(MyStraxPlugin)
ctx.register(adapter)
```

### 3. 批量处理
```python
from waveform_analysis.core.data import BatchProcessor

processor = BatchProcessor(ctx)
results = processor.process_runs(['run_001', 'run_002'], 'peaks', max_workers=4)
```

### 4. 数据导出
```python
from waveform_analysis.core.data import DataExporter

exporter = DataExporter()
exporter.export(data, 'output.parquet')
```

### 5. 热重载
```python
from waveform_analysis.core.hot_reload import enable_hot_reload

reloader = enable_hot_reload(ctx, ['my_plugin'], auto_reload=True)
```

---

## 📖 详细文档链接

- **完整新功能文档**: `docs/NEW_FEATURES.md`
- **开发指南**: `AGENTS.md` 与 `docs/agents/`
- **变更日志**: `CHANGELOG.md`
- **测试用例**: `tests/test_time_range_query.py`, `tests/test_strax_adapter.py`

---

## ✅ 测试状态

| 模块 | 测试文件 | 状态 | 覆盖率 |
|------|---------|------|--------|
| 时间范围查询 | test_time_range_query.py | ✅ 7/7 通过 | 56% |
| Strax适配器 | test_strax_adapter.py | ✅ 核心功能通过 | 79% |
| 批量处理 | (集成在core.data) | ✅ | - |
| 数据导出 | (集成在core.data) | ✅ | - |
| 热重载 | (手动测试) | ✅ | - |



## 💡 使用建议

### 性能优化
1. **时间查询**: 首次 time_range 会自动构建索引，后续查询更快
2. **批量处理**: 根据任务类型选择合适的worker数量
3. **数据导出**: 优先使用Parquet格式

### 最佳实践
1. **Strax集成**: 使用`is_compatible()`检查插件兼容性
2. **批量处理**: 使用`on_error='continue'`避免单点故障
3. **热重载**: 仅在开发环境启用

---

## 🐛 常见问题

### Q: 时间查询比直接过滤慢？
**A**: 首次查询会自动构建索引，之后会更快。直接使用 `time_range()` 即可。

### Q: Strax插件无法注册？
**A**: 确保插件有`provides`和`compute`方法。使用`adapter.is_compatible()`检查。

### Q: 批量处理失败？
**A**: 使用`on_error='continue'`继续处理，在`results['errors']`查看错误。

### Q: 导出文件太大？
**A**: 使用Parquet格式并启用压缩：`compression='snappy'`

---

## 🔗 相关链接

- [项目主页](https://github.com/yourusername/waveform-analysis)
- [问题追踪](https://github.com/yourusername/waveform-analysis/issues)
- [贡献指南](../../development/contributing/README.md)

---

**最后更新**: 2026-01-09
**版本**: None
