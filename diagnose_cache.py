#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存诊断脚本 - 检查为什么 st_waveforms 没有被跳过
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    WaveformsPlugin,
    StWaveformsPlugin,
    FilteredWaveformsPlugin,
)

# 使用你的 run_name
run_name = "Argon_w4_o3_Window_27dB_75LSB_annode2300_cathode1200_0116"

# 创建 Context
ctx = Context(config={"data_root": "DAQ", "n_channels": 2})

# 注册插件
ctx.register(WaveformsPlugin())
ctx.register(StWaveformsPlugin())
ctx.register(FilteredWaveformsPlugin())

print("=" * 70)
print("缓存诊断报告")
print("=" * 70)

# 1. 检查缓存文件是否存在
print(f"\n1. 检查缓存文件存在性:")
print(f"   Run ID: {run_name}")

for data_name in ["waveforms", "st_waveforms", "filtered_waveforms"]:
    key = ctx.key_for(run_name, data_name)

    # 检查单通道数据
    exists_single = ctx.storage.exists(key, run_name)

    # 检查多通道数据
    exists_multi = ctx.storage.exists(f"{key}_ch0", run_name)

    print(f"\n   {data_name}:")
    print(f"     单通道缓存: {'✓ 存在' if exists_single else '✗ 不存在'}")
    print(f"     多通道缓存: {'✓ 存在' if exists_multi else '✗ 不存在'}")

    if exists_single or exists_multi:
        # 检查元数据
        try:
            meta = ctx.storage.load_metadata(key, run_name)
            print(f"     元数据:")
            print(f"       - 版本: {meta.get('version', 'N/A')}")
            print(f"       - 类型: {meta.get('type', 'N/A')}")
            if 'lineage' in meta:
                print(f"       - Lineage: {meta['lineage'][:50]}..." if len(meta['lineage']) > 50 else f"       - Lineage: {meta['lineage']}")
        except Exception as e:
            print(f"     元数据读取失败: {e}")

# 2. 检查 lineage 是否匹配
print(f"\n2. 检查 Lineage 匹配:")

for data_name in ["st_waveforms"]:
    plugin = ctx._plugins.get(data_name)
    if not plugin:
        continue

    key = ctx.key_for(run_name, data_name)

    # 计算当前 lineage
    current_lineage = ctx.lineage_hash(plugin, run_name)

    # 读取缓存的 lineage
    try:
        meta = ctx.storage.load_metadata(key, run_name)
        cached_lineage = meta.get('lineage', '')

        print(f"\n   {data_name}:")
        print(f"     当前 lineage: {current_lineage}")
        print(f"     缓存 lineage: {cached_lineage}")
        print(f"     匹配: {'✓ 是' if current_lineage == cached_lineage else '✗ 否'}")

        if current_lineage != cached_lineage:
            print(f"     ⚠️  Lineage 不匹配，缓存将被重新计算")

    except Exception as e:
        print(f"\n   {data_name}: 无法读取元数据 ({e})")

# 3. 检查内存缓存
print(f"\n3. 检查内存缓存:")
for data_name in ["waveforms", "st_waveforms", "filtered_waveforms"]:
    mem_data = ctx._get_data_from_memory(run_name, data_name)
    print(f"   {data_name}: {'✓ 在内存中' if mem_data is not None else '✗ 不在内存中'}")

# 4. 预览执行计划
print(f"\n4. 执行计划预览:")
try:
    result = ctx.preview_execution(run_name, "filtered_waveforms", verbose=0)
    print(f"\n   执行计划: {' → '.join(result['execution_plan'])}")
    print(f"\n   缓存状态:")
    for plugin_name, status in result['cache_status'].items():
        needs_compute = "需要计算" if status['needs_compute'] else "缓存命中"
        print(f"     {plugin_name}: {needs_compute}")
        if status['needs_compute'] and 'reason' in status:
            print(f"       原因: {status['reason']}")
except Exception as e:
    print(f"   预览失败: {e}")

print("\n" + "=" * 70)
print("诊断完成")
print("=" * 70)
