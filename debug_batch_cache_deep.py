#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
深度调试 BatchProcessor 缓存问题

通过 monkey patch 追踪 get_data 调用和缓存状态变化
"""

import time
from functools import wraps


def patch_context_for_debugging(ctx):
    """
    给 Context 添加调试日志，追踪缓存访问

    Args:
        ctx: Context 对象
    """
    # 保存原始方法
    original_get_data = ctx.get_data
    original_get_data_from_memory = ctx._get_data_from_memory
    original_load_from_disk = ctx._load_from_disk_with_check
    original_run_plugin = ctx.run_plugin

    call_counter = {'count': 0}

    @wraps(ctx.get_data)
    def debug_get_data(run_id, data_name, **kwargs):
        call_counter['count'] += 1
        call_id = call_counter['count']

        print(f"\n{'='*80}")
        print(f"🔍 [Call #{call_id}] get_data(run_id='{run_id}', data_name='{data_name}')")
        print(f"{'='*80}")

        # 检查缓存状态
        cache_key = (run_id, data_name)
        in_memory_before = cache_key in ctx._results
        print(f"  📦 内存缓存（调用前）: {'✅ 存在' if in_memory_before else '❌ 不存在'}")

        if in_memory_before:
            data = ctx._results[cache_key]
            print(f"     └─ 类型: {type(data).__name__}")
            if hasattr(data, '__len__'):
                print(f"     └─ 大小: {len(data):,} 条")

        # 调用原始方法
        start_time = time.time()
        result = original_get_data(run_id, data_name, **kwargs)
        elapsed = time.time() - start_time

        # 检查缓存状态（调用后）
        in_memory_after = cache_key in ctx._results
        print(f"  📦 内存缓存（调用后）: {'✅ 存在' if in_memory_after else '❌ 不存在'}")
        print(f"  ⏱️  执行时间: {elapsed:.3f}s")

        # 判断是否使用了缓存
        if elapsed < 0.1:
            print(f"  ✅ 缓存命中（快速返回）")
        elif elapsed < 2.0:
            print(f"  ⚠️  可能从磁盘加载")
        else:
            print(f"  ❌ 重新计算（慢！）")

        print(f"{'='*80}\n")
        return result

    @wraps(ctx._get_data_from_memory)
    def debug_get_data_from_memory(run_id, name):
        result = original_get_data_from_memory(run_id, name)
        cache_key = (run_id, name)
        status = "✅ 命中" if result is not None else "❌ 未命中"
        print(f"    ├─ _get_data_from_memory: {status}")
        return result

    @wraps(ctx._load_from_disk_with_check)
    def debug_load_from_disk(run_id, name, key):
        print(f"    ├─ _load_from_disk_with_check: 检查中...")
        result = original_load_from_disk(run_id, name, key)
        status = "✅ 命中" if result is not None else "❌ 未命中"
        print(f"    │  └─ 结果: {status}")
        return result

    @wraps(ctx.run_plugin)
    def debug_run_plugin(run_id, data_name, **kwargs):
        print(f"    └─ 🔧 run_plugin: 开始执行插件计算")
        result = original_run_plugin(run_id, data_name, **kwargs)
        print(f"       └─ ✓ 计算完成")
        return result

    # 应用 monkey patch
    ctx.get_data = debug_get_data
    ctx._get_data_from_memory = debug_get_data_from_memory
    ctx._load_from_disk_with_check = debug_load_from_disk
    ctx.run_plugin = debug_run_plugin

    print("✅ 已启用调试模式")
    print("   所有 get_data 调用都会被追踪")
    print()


def unpatch_context(ctx, original_methods):
    """恢复原始方法"""
    ctx.get_data = original_methods['get_data']
    ctx._get_data_from_memory = original_methods['_get_data_from_memory']
    ctx._load_from_disk_with_check = original_methods['_load_from_disk_with_check']
    ctx.run_plugin = original_methods['run_plugin']
    print("✅ 已禁用调试模式")


def test_batch_processor_with_debug(ctx, run_ids, data_name):
    """
    使用调试模式测试 BatchProcessor

    Args:
        ctx: Context 对象
        run_ids: 要测试的 run_id 列表
        data_name: 数据名称
    """
    from waveform_analysis.core.data.export import BatchProcessor

    print("\n" + "="*80)
    print("🧪 调试模式：测试 BatchProcessor")
    print("="*80)

    # 启用调试
    patch_context_for_debugging(ctx)

    # 确认缓存状态
    print("\n📊 当前内存缓存状态:")
    print("-"*80)
    for run_id in run_ids:
        cache_key = (run_id, data_name)
        exists = cache_key in ctx._results
        print(f"  {run_id}: {'✅ 已缓存' if exists else '❌ 未缓存'}")

    print("\n" + "="*80)
    print("🚀 开始 BatchProcessor 测试")
    print("="*80)

    # 创建 BatchProcessor 并执行
    batch_processor = BatchProcessor(ctx)

    try:
        results = batch_processor.process_runs(
            run_ids=run_ids,
            data_name=data_name,
            show_progress=True,
            max_workers=2,  # 并行执行
        )

        print("\n" + "="*80)
        print("📊 BatchProcessor 结果:")
        print("="*80)
        print(f"  成功: {len(results['results'])} 个")
        print(f"  失败: {len(results['errors'])} 个")

        for run_id, df_run in results['results'].items():
            print(f"    ✓ {run_id}: {len(df_run):,} 条记录")

        if results['errors']:
            print(f"  ⚠️  错误:")
            for run_id, error in results['errors'].items():
                print(f"    ✗ {run_id}: {error}")

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


def simple_test_cache_hit(ctx, run_id, data_name):
    """
    简单测试：直接调用 get_data 两次，看是否命中缓存

    Args:
        ctx: Context 对象
        run_id: 运行ID
        data_name: 数据名称
    """
    print("\n" + "="*80)
    print("🧪 简单缓存测试：连续两次 get_data 调用")
    print("="*80)

    # 启用调试
    patch_context_for_debugging(ctx)

    print("\n📥 第一次调用 get_data:")
    data1 = ctx.get_data(run_id, data_name)

    print("\n📥 第二次调用 get_data:")
    data2 = ctx.get_data(run_id, data_name)

    print("\n" + "="*80)
    print("📊 结果比较:")
    print("="*80)
    print(f"  第一次返回: {type(data1).__name__}, {len(data1):,} 条")
    print(f"  第二次返回: {type(data2).__name__}, {len(data2):,} 条")
    print(f"  对象相同: {'✅ 是' if data1 is data2 else '❌ 否'}")

    if data1 is data2:
        print("\n✅ 缓存正常工作！第二次调用直接返回了缓存对象")
    else:
        print("\n⚠️  警告：两次调用返回了不同的对象，可能未使用缓存")


if __name__ == "__main__":
    print("""
使用方法：

1. 简单测试（推荐先运行）：

```python
from debug_batch_cache_deep import simple_test_cache_hit

# 测试单个 run_id 的缓存
simple_test_cache_hit(ctx, "Co60_R50", "df_events_with_code")
```

2. 完整调试 BatchProcessor：

```python
from debug_batch_cache_deep import test_batch_processor_with_debug

# 调试 BatchProcessor
run_ids = ["Co60_R50", "All_SelfTrigger"]
test_batch_processor_with_debug(ctx, run_ids, "df_events_with_code")
```

3. 手动启用调试模式：

```python
from debug_batch_cache_deep import patch_context_for_debugging

# 启用调试
patch_context_for_debugging(ctx)

# 然后正常使用 ctx.get_data 或 BatchProcessor
# 所有调用都会被追踪并打印详细日志
```
""")
