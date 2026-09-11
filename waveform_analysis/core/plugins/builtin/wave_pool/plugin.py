"""WavePoolPlugin 类实现 - 从共享 RecordsBundle 暴露 wave_pool。

单向依赖 ``records`` bundle 的共享计算（``_RecordsBundlePluginBase`` 与
``get_records_bundle`` / ``_wave_pool_from_bundle``）。
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.records._compute import (
    _RecordsBundlePluginBase,
    _wave_pool_from_bundle,
    get_records_bundle,
)


class WavePoolPlugin(_RecordsBundlePluginBase):
    """Expose wave_pool as a formal plugin output backed by RecordsBundle."""

    provides = "wave_pool"
    lineage_virtual = True
    depends_on = []
    description = "Build wave_pool from the shared internal records bundle."
    output_dtype = np.dtype(np.uint16)
    agent_doc = {
        "overview": (
            "WavePoolPlugin 把共享 RecordsBundle 中的原始 ADC 波形样本暴露为正式的 `wave_pool` "
            "插件输出。wave_pool 是一维 uint16 数组，事件波形通过 `records['wave_offset']` 与 "
            "`records['event_length']` 切片获得，因此它必须与 `records` 保持行对齐的索引约定。\n\n"
            "与 `records` 一样，wave_pool 复用同一份内存或磁盘 bundle：单分片 `RecordsBundleRef` "
            "时直接 memmap `wave_pool_path`，避免二次拷贝；`lineage_virtual=True` 标记其血缘推导为"
            "虚拟，配置与血缘共享 `records` 插件的来源，避免两处配置漂移。\n\n"
            "它是 records-backed 波形访问与滤波产物（如 `wave_pool_filtered`）的直接数据源，也是"
            " peaklet 波形还原（peaklet_waveforms，在 use_filtered=False 时）的原始波形池。"
        ),
        "workflow_steps": [
            "解析共享 bundle：调用 `get_records_bundle(context, run_id)` 获取本 run 的 RecordsBundle / RecordsBundleRef。",
            "选择波形池视图：`RecordsBundleRef` 单分片时直接 memmap `wave_pool_path`（uint16, shape=(n_samples,)），内存 bundle 直接返回 `bundle.wave_pool`。",
            "返回结果：输出一维 uint16 数组，供 `records` 的 `wave_offset`/`event_length` 切片访问。",
        ],
        "behavior_notes": [
            "The returned array is a flat `uint16` pool; per-event waveforms are slices `pool[offset : offset + length]`.",
            "`wave_pool` is paired 1:1 with `records` through `wave_offset`/`event_length`; keeping both plugins consistent is part of the shared bundle contract.",
            "Config resolution follows the `records` plugin (`_resolve_bundle_config_plugin`) so the two outputs never drift in dtype/dt/bundle semantics.",
        ],
        "config_notes": {
            "daq_adapter": "DAQ 适配器名称，决定 bundle 的解析路径（vx2730/v1725 等）；与 records 共享。",
            "keep_on_disk": "是否保持 bundle 磁盘驻留；None 时 V1725 默认 True、其余适配器默认 False。",
            "dt": "采样间隔（ns），写回 records.dt；缺省取适配器采样率或 1ns。",
            "baseline_samples": "基线范围（int 或 (start, end)），在 bundle 构建时同步用于 records。",
            "input_source": "records bundle 输入源：raw_files 或 st_waveforms（V1725 仅支持 raw_files）。",
        },
        "failure_modes": [
            "`RecordsBundleRef` 为多分片且未合并为单分片视图时，`_wave_pool_from_bundle` 抛出 `ValueError`（wave_pool 要求单分片 memmap 视图）。",
            "上游 bundle 缺失或 `input_source` 非法时，由共享 bundle 构建逻辑抛出 `ValueError`。",
        ],
        "downstream_consumers": [
            "records_asymmetry_mask",
            "wave_pool_filtered",
            "peaklet_waveforms",
        ],
        "downstream_notes": [
            "`wave_pool_filtered` 以 wave_pool 为输入做滤波，输出同为 records 对齐的 float32 池。",
            "`peaklet_waveforms` 在 `use_filtered=False` 时直接消费 wave_pool；池的索引约定必须与 records 保持一致。",
        ],
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        bundle = get_records_bundle(context, run_id)
        return _wave_pool_from_bundle(bundle)


__all__ = ["WavePoolPlugin"]
