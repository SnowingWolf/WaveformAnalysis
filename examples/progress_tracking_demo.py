#!/usr/bin/env python
"""
进度追踪系统使用示例

演示如何使用统一的进度追踪装饰器 @with_progress
"""

import time

from waveform_analysis.core.foundation.progress import (
    ProgressTracker,
    get_global_tracker,
    progress_iter,
    progress_map,
    with_progress,
)

# ===========================
# 示例1: 装饰生成器函数
# ===========================


@with_progress(total=100, desc="Processing items", unit="item")
def generate_items():
    """生成器函数自动显示进度"""
    for i in range(100):
        time.sleep(0.01)  # 模拟处理
        yield i * 2


# ===========================
# 示例2: 装饰返回列表的函数
# ===========================


@with_progress(desc="Loading files", unit="file")
def load_files(file_list):
    """返回可迭代对象的函数自动包装"""
    results = []
    for file in file_list:
        time.sleep(0.05)
        results.append(f"content_of_{file}")
    return results


# ===========================
# 示例3: 普通函数显示执行时间
# ===========================


@with_progress(desc="Computing", show_result=True)
def expensive_computation(n):
    """普通函数显示执行时间"""
    time.sleep(1)
    return sum(range(n))


# ===========================
# 示例4: 使用 progress_iter
# ===========================


def process_with_progress_iter():
    """使用 progress_iter 包装可迭代对象"""
    data = range(50)

    results = []
    for item in progress_iter(data, desc="Processing data", unit="item"):
        time.sleep(0.02)
        results.append(item**2)

    return results


# ===========================
# 示例5: 使用 progress_map
# ===========================


def process_with_progress_map():
    """使用 progress_map 应用函数"""
    data = range(50)

    def square(x):
        time.sleep(0.02)
        return x**2

    return progress_map(square, data, desc="Squaring numbers")


# ===========================
# 示例6: 嵌套进度条
# ===========================


def process_batches():
    """演示嵌套进度条"""
    tracker = get_global_tracker()

    # 创建主进度条
    tracker.create_bar("batches", total=5, desc="Processing batches", unit="batch")

    for batch_id in range(5):
        # 创建嵌套进度条
        bar_name = f"batch_{batch_id}"
        tracker.create_bar(
            bar_name, total=20, desc=f"Batch {batch_id}", unit="item", nested=True, parent="batches"
        )

        # 处理批次中的项目
        for _i in range(20):
            time.sleep(0.01)
            tracker.update(bar_name, n=1)

        # 关闭嵌套进度条
        tracker.close(bar_name)

        # 更新主进度条
        tracker.update("batches", n=1)

    # 关闭主进度条
    tracker.close("batches")


# ===========================
# 示例7: 自定义进度追踪器
# ===========================


@with_progress(desc="Custom processing", unit="item")
def process_with_custom_tracker(items, tracker=None):
    """使用自定义追踪器"""
    for item in items:
        time.sleep(0.02)
        yield item * 3


# ===========================
# 主函数
# ===========================


def main():
    """运行所有示例"""

    print("=" * 60)
    print("示例1: 装饰生成器函数")
    print("=" * 60)
    result1 = list(generate_items())
    print(f"Generated {len(result1)} items\n")

    print("=" * 60)
    print("示例2: 装饰返回列表的函数")
    print("=" * 60)
    files = [f"file_{i}.csv" for i in range(10)]
    result2 = list(load_files(files))
    print(f"Loaded {len(result2)} files\n")

    print("=" * 60)
    print("示例3: 普通函数显示执行时间")
    print("=" * 60)
    result3 = expensive_computation(1000000)
    print(f"Computation result: {result3}\n")

    print("=" * 60)
    print("示例4: 使用 progress_iter")
    print("=" * 60)
    result4 = process_with_progress_iter()
    print(f"Processed {len(result4)} items\n")

    print("=" * 60)
    print("示例5: 使用 progress_map")
    print("=" * 60)
    result5 = process_with_progress_map()
    print(f"Mapped {len(result5)} items\n")

    print("=" * 60)
    print("示例6: 嵌套进度条")
    print("=" * 60)
    process_batches()
    print("Batch processing completed\n")

    print("=" * 60)
    print("示例7: 自定义进度追踪器")
    print("=" * 60)
    custom_tracker = ProgressTracker()
    items = range(30)
    result7 = list(process_with_custom_tracker(items, tracker=custom_tracker))
    print(f"Processed {len(result7)} items with custom tracker\n")

    print("=" * 60)
    print("所有示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
