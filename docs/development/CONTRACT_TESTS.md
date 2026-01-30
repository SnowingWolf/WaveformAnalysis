# 合同测试 (Contract Tests)

合同测试用于验证插件系统的核心契约，确保：
- 插件契约完整且可校验
- 缓存行为一致
- 兼容层正确工作
- 标准数据流端到端可用

## 测试位置

```
tests/contracts/
├── __init__.py
├── conftest.py                    # 共享 fixtures
├── test_plugin_contracts.py       # 插件契约测试
├── test_cache_consistency.py      # 缓存一致性测试
├── test_compat_deprecation.py     # 兼容/弃用测试
└── test_golden_path.py            # 黄金链路测试
```

## 运行测试

```bash
# 运行所有合同测试
pytest tests/contracts/ -v

# 运行特定类别
pytest tests/contracts/test_plugin_contracts.py -v
pytest tests/contracts/test_cache_consistency.py -v
pytest tests/contracts/test_compat_deprecation.py -v
pytest tests/contracts/test_golden_path.py -v
```

## 测试类别

### 1. 插件契约测试 (`test_plugin_contracts.py`)

验证所有 builtin 插件遵循契约规范。

| 测试类 | 验证内容 |
|--------|----------|
| `TestPluginSpecExtraction` | 所有插件可提取 PluginSpec |
| `TestOutputSchemaCompleteness` | 输出 schema 完整且可序列化 |
| `TestConfigSpecCompleteness` | 配置 spec 与 options 匹配 |
| `TestDependencyGraph` | 依赖图无环、provides 唯一 |
| `TestSpecValidation` | spec.validate() 通过 |
| `TestRegistrationWithSpec` | require_spec=True 注册行为 |

**关键断言**：
- 每个 builtin 插件必须有可提取的 `PluginSpec`
- `output_schema` 必须 JSON 可序列化（用于 lineage）
- `depends_on` 无循环依赖
- `provides` 在所有插件中唯一

### 2. 缓存一致性测试 (`test_cache_consistency.py`)

验证缓存 key 生成和命中/失效逻辑。

| 测试类 | 验证内容 |
|--------|----------|
| `TestCacheKeyGeneration` | 缓存 key 生成规则 |
| `TestLineageHash` | Lineage hash 包含版本信息 |
| `TestConfigChangeInvalidatesCache` | 配置变化使缓存失效 |
| `TestCacheHitMissBehavior` | 实际缓存命中/失效行为 |
| `TestWatchSignature` | 文件变化检测 |

**关键断言**：
- 相同 `(run_id, config, version)` → 相同缓存 key
- 任意关键配置变化 → 不同缓存 key
- `track=False` 的配置不影响缓存 key
- 插件版本变化 → 缓存失效

### 3. 兼容/弃用测试 (`test_compat_deprecation.py`)

验证 `CompatManager` 的别名和弃用处理。

| 测试类 | 验证内容 |
|--------|----------|
| `TestAliasResolution` | 别名解析正确 |
| `TestDeprecationWarnings` | 弃用警告发出 |
| `TestDeprecationExpiry` | 过期弃用抛出错误 |
| `TestCompatManagerAPI` | API 按文档工作 |
| `TestRegisterUnregister` | 动态注册/注销 |
| `TestDeprecationInfoDataclass` | DeprecationInfo 数据类 |

**关键断言**：
- `old_name` → `canonical_name` 解析正确
- 弃用窗口期：发出 `DeprecationWarning`
- 过期后（`current_version >= removed_in`）：抛出 `ValueError`
- 实例化后注册的弃用信息对已有实例可见

### 4. 黄金链路测试 (`test_golden_path.py`)

验证标准数据流端到端工作。

| 测试类 | 验证内容 |
|--------|----------|
| `TestGoldenPathMinimal` | 最小 pipeline 执行 |
| `TestGoldenPathWithBuiltinPlugins` | 内置插件集成 |
| `TestGoldenPathErrorHandling` | 错误处理 |
| `TestGoldenPathCaching` | 缓存行为 |

**关键断言**：
- `raw_files → waveforms → st_waveforms → basic_features` 链路可执行
- 中间数据可访问
- 依赖按正确顺序计算
- 错误正确传播（包装在 `RuntimeError` 中）

## 添加新测试

### 添加插件契约测试

当添加新的 builtin 插件时，现有测试会自动覆盖（通过 `all_builtin_plugins` fixture）。

如需添加特定插件测试：

```python
def test_my_plugin_specific_contract(self, context):
    from waveform_analysis.core.plugins.builtin.cpu import MyPlugin

    plugin = MyPlugin()
    spec = PluginSpec.from_plugin(plugin)

    # 验证特定契约
    assert spec.capabilities.supports_streaming is True
    assert "my_config" in spec.config_spec
```

### 添加缓存测试

```python
def test_my_cache_scenario(self, temp_storage_dir):
    class MyPlugin(Plugin):
        provides = "my_data"
        # ...

    ctx = Context(storage_dir=str(temp_storage_dir))
    ctx.register(MyPlugin())

    key1 = ctx.key_for("run_001", "my_data")
    # 修改配置
    ctx.set_config({"param": "new_value"}, plugin_name="my_data")
    key2 = ctx.key_for("run_001", "my_data")

    assert key1 != key2  # 配置变化应导致不同 key
```

### 添加兼容性测试

```python
def test_my_deprecation(self):
    CompatManager.register_deprecation(DeprecationInfo(
        old_name="old_param",
        new_name="new_param",
        deprecated_in="1.0.0",
        removed_in="2.0.0",
    ))

    manager = CompatManager()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        manager.warn_deprecation("old_param")
        assert len(w) >= 1
```

## CI 集成

合同测试应在 CI 中运行，任何契约破坏都会导致构建失败：

```yaml
# .github/workflows/test.yml
- name: Run contract tests
  run: pytest tests/contracts/ -v --tb=short
```

## 相关文档

- [PluginSpec 指南](plugin-development/PLUGIN_SPEC_GUIDE.md) - 插件契约规范
- [配置系统](../features/context/CONFIGURATION.md) - 配置管理
- [缓存管理](../features/context/DATA_ACCESS.md) - 缓存行为
