"""
builtin.shared - 跨插件通用共享库

供多个插件家族（cpu/hit/peaks/streaming）复用的纯计算工具模块：

- ``dt_compat``: 采样间隔配置迁移 helper
- ``record_utils``: record lookup 与字段访问
- ``wave_source``: 波形数据源选择与加载

非 bundle：本包不包含插件类。
"""
