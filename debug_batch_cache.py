#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BatchProcessor 缓存诊断脚本

用于诊断为什么 BatchProcessor 会重新计算已经加载过的数据
"""

def diagnose_cache_status(ctx, run_ids, data_name):
    """
    诊断缓存状态

    Args:
        ctx: Context 对象
        run_ids: 要检查的 run_id 列表
        data_name: 数据名称
    """
    print("=" * 80)
    print(f"🔍 缓存诊断：{data_name}")
    print("=" * 80)

    for run_id in run_ids:
        print(f"\n📦 Run ID: {run_id}")
        print("-" * 80)

        # 1. 检查内存缓存
        cache_key = (run_id, data_name)
        in_memory = cache_key in ctx._results
        print(f"  1️⃣  内存缓存: {'✅ 存在' if in_memory else '❌ 不存在'}")

        if in_memory:
            data = ctx._results[cache_key]
            if hasattr(data, '__len__'):
                print(f"      └─ 数据大小: {len(data):,} 条记录")
            print(f"      └─ 数据类型: {type(data).__name__}")

        # 2. 检查磁盘缓存
        if data_name in ctx._plugins:
            key = ctx.key_for(run_id, data_name)
            on_disk = ctx.storage.exists(key, run_id)
            print(f"  2️⃣  磁盘缓存: {'✅ 存在' if on_disk else '❌ 不存在'}")

            if on_disk:
                meta = ctx.storage.get_metadata(key, run_id)
                if meta:
                    print(f"      └─ 缓存文件: {key}")
                    if 'lineage' in meta:
                        # 检查 lineage 是否匹配
                        current_lineage = ctx.get_lineage(data_name)
                        import json
                        cached_lineage_str = json.dumps(meta['lineage'], sort_keys=True, default=str)
                        current_lineage_str = json.dumps(current_lineage, sort_keys=True, default=str)
                        lineage_match = (cached_lineage_str == current_lineage_str)
                        print(f"      └─ Lineage 匹配: {'✅ 一致' if lineage_match else '❌ 不一致（会触发重新计算）'}")

                        if not lineage_match:
                            print(f"      └─ ⚠️  Lineage 差异分析:")
                            print(f"          缓存版本: {meta['lineage'].get('version', 'N/A')}")
                            print(f"          当前版本: {current_lineage.get('version', 'N/A')}")
        else:
            print(f"  2️⃣  磁盘缓存: ⚠️  '{data_name}' 不是插件提供的数据")

        # 3. 检查 run_id 格式
        print(f"  3️⃣  Run ID 格式检查:")
        print(f"      └─ 长度: {len(run_id)} 字符")
        print(f"      └─ 包含空格: {'是' if ' ' in run_id else '否'}")
        print(f"      └─ repr: {repr(run_id)}")

        # 4. 显示所有相关的内存缓存键
        related_keys = [k for k in ctx._results.keys() if k[0] == run_id or k[1] == data_name]
        if related_keys:
            print(f"  4️⃣  相关内存缓存键:")
            for k in related_keys[:5]:  # 只显示前5个
                print(f"      └─ {k}")
            if len(related_keys) > 5:
                print(f"      └─ ... 还有 {len(related_keys) - 5} 个")

    print("\n" + "=" * 80)
    print("💡 诊断完成")
    print("=" * 80)


def test_batch_processor_cache(ctx, run_ids, data_name):
    """
    测试 BatchProcessor 是否正确使用缓存

    Args:
        ctx: Context 对象
        run_ids: 要测试的 run_id 列表
        data_name: 数据名称
    """
    from waveform_analysis.core.data.export import BatchProcessor
    import time

    print("\n" + "=" * 80)
    print(f"🧪 测试 BatchProcessor 缓存机制")
    print("=" * 80)

    # 先手动加载一次，确保缓存存在
    print(f"\n📥 第一次加载：手动通过 Context.get_data() 加载")
    print("-" * 80)
    for run_id in run_ids:
        print(f"  ⏳ 加载 {run_id}...", end=" ")
        start = time.time()
        data = ctx.get_data(run_id, data_name)
        elapsed = time.time() - start
        print(f"✓ ({elapsed:.2f}s, {len(data):,} 条记录)")

    # 诊断缓存状态
    diagnose_cache_status(ctx, run_ids, data_name)

    # 使用 BatchProcessor 加载
    print(f"\n📥 第二次加载：使用 BatchProcessor 加载")
    print("-" * 80)

    batch_processor = BatchProcessor(ctx)
    start = time.time()
    results = batch_processor.process_runs(
        run_ids=run_ids,
        data_name=data_name,
        show_progress=True,
        max_workers=2,
    )
    total_elapsed = time.time() - start

    print(f"\n📊 BatchProcessor 结果:")
    print("-" * 80)
    print(f"  总耗时: {total_elapsed:.2f}s")
    print(f"  成功: {len(results['results'])} 个")
    print(f"  失败: {len(results['errors'])} 个")

    # ✅ 正确的遍历方式
    for run_id, df_run in results['results'].items():
        print(f"    ✓ {run_id}: {len(df_run):,} 条记录")

    if results['errors']:
        print(f"  ⚠️  错误:")
        for run_id, error in results['errors'].items():
            print(f"    ✗ {run_id}: {error}")

    # 分析性能
    print(f"\n💡 性能分析:")
    print("-" * 80)
    avg_time_per_run = total_elapsed / len(run_ids)
    print(f"  平均每个 run: {avg_time_per_run:.2f}s")
    if avg_time_per_run < 1.0:
        print(f"  ✅ 使用了缓存（每个 run < 1s）")
    else:
        print(f"  ⚠️  可能未使用缓存（每个 run > 1s）")


if __name__ == "__main__":
    print("""
使用方法：

1. 在 Jupyter Notebook 中运行：

```python
from debug_batch_cache import diagnose_cache_status, test_batch_processor_cache

# 诊断当前缓存状态
run_ids = ["Co60_R50", "All_SelfTrigger"]
diagnose_cache_status(ctx, run_ids, "df_events_with_code")

# 完整测试 BatchProcessor 缓存
test_batch_processor_cache(ctx, run_ids, "df_events_with_code")
```

2. 如果发现缓存未命中，检查：
   - run_id 是否完全一致（大小写、空格）
   - 是否在两次调用之间修改了插件代码
   - 是否手动清空了缓存
""")
