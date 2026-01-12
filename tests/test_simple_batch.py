#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版批量处理测试 - 不使用进度条和取消令牌
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def simple_batch_process(ctx, run_ids, data_name, max_workers=2):
    """
    最简化的批量处理（不使用进度条、取消令牌等复杂功能）

    Args:
        ctx: Context 对象
        run_ids: 运行ID列表
        data_name: 数据名称
        max_workers: 并行工作线程数

    Returns:
        结果字典
    """
    print("=" * 80)
    print("🧪 简化版批量处理测试")
    print("=" * 80)

    results = {}
    errors = {}
    start_time = time.time()

    if max_workers == 1:
        # 串行处理
        print("\n📥 串行处理模式:")
        print("-" * 80)
        for i, run_id in enumerate(run_ids):
            print(f"  [{i+1}/{len(run_ids)}] 加载 {run_id}...", end=" ", flush=True)
            t0 = time.time()
            try:
                data = ctx.get_data(run_id, data_name)
                results[run_id] = data
                elapsed = time.time() - t0
                print(f"✓ ({elapsed:.3f}s, {len(data):,} 条)")
            except Exception as e:
                errors[run_id] = e
                elapsed = time.time() - t0
                print(f"✗ ({elapsed:.3f}s, 错误: {e})")
    else:
        # 并行处理
        print(f"\n📥 并行处理模式 (max_workers={max_workers}):")
        print("-" * 80)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            print(f"  提交 {len(run_ids)} 个任务...")
            future_to_run = {}
            for run_id in run_ids:
                print(f"    └─ 提交任务: {run_id}")
                future = executor.submit(ctx.get_data, run_id, data_name)
                future_to_run[future] = run_id

            print(f"  所有任务已提交，等待完成...")
            print()

            # 收集结果
            completed_count = 0
            for future in as_completed(future_to_run):
                run_id = future_to_run[future]
                completed_count += 1

                print(f"  [{completed_count}/{len(run_ids)}] {run_id}: ", end="", flush=True)

                try:
                    data = future.result(timeout=120)  # 2分钟超时
                    results[run_id] = data
                    print(f"✓ ({len(data):,} 条)")
                except TimeoutError:
                    errors[run_id] = "Timeout after 120s"
                    print(f"✗ 超时")
                except Exception as e:
                    errors[run_id] = e
                    print(f"✗ 错误: {e}")

    total_elapsed = time.time() - start_time

    print()
    print("=" * 80)
    print("📊 结果统计:")
    print("=" * 80)
    print(f"  总耗时: {total_elapsed:.3f}s")
    print(f"  成功: {len(results)} 个")
    print(f"  失败: {len(errors)} 个")
    print(f"  平均每个: {total_elapsed / len(run_ids):.3f}s")

    if total_elapsed / len(run_ids) < 0.5:
        print(f"  ✅ 性能正常（使用了缓存）")
    else:
        print(f"  ⚠️  性能较慢（可能未使用缓存）")

    if results:
        print(f"\n  成功的 run:")
        for run_id, data in results.items():
            print(f"    ✓ {run_id}: {len(data):,} 条")

    if errors:
        print(f"\n  失败的 run:")
        for run_id, error in errors.items():
            print(f"    ✗ {run_id}: {error}")

    print("=" * 80)

    return {'results': results, 'errors': errors}


if __name__ == "__main__":
    print("""
使用方法：

```python
from test_simple_batch import simple_batch_process

run_ids = ["Co60_R50", "All_SelfTrigger"]

# 串行测试
result = simple_batch_process(ctx, run_ids, "df_events_with_code", max_workers=1)

# 并行测试
result = simple_batch_process(ctx, run_ids, "df_events_with_code", max_workers=2)
```
""")
