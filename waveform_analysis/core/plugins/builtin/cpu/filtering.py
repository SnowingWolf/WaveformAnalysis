# -*- coding: utf-8 -*-
"""
CPU Filtering Plugin - 使用 scipy 进行波形滤波

**加速器**: CPU (scipy)
**功能**: 波形滤波（Butterworth 带通滤波、Savitzky-Golay 滤波）

本插件提供两种滤波方法：
- Butterworth 带通滤波器 (BW)
- Savitzky-Golay 滤波器 (SG)
"""

import logging
from typing import Any, List, Optional

import numpy as np
from scipy.signal import butter, savgol_filter, sosfiltfilt

from waveform_analysis.core.plugins.core.base import Option, Plugin

logger = logging.getLogger(__name__)


class FilteredWaveformsPlugin(Plugin):
    provides = "filtered_waveforms"
    depends_on = ["st_waveforms"]
    description = "Apply filtering to waveforms using Butterworth or Savitzky-Golay filters."
    version = "1.0.2"
    save_when = "target"

    options = {
        "filter_type": Option(default="SG", type=str, help="滤波器类型: 'BW' 或 'SG'"),
        "lowcut": Option(default=0.1, type=float, help="BW 低频截止"),
        "highcut": Option(default=0.5, type=float, help="BW 高频截止"),
        "fs": Option(default=0.5, type=float, help="BW 采样率（GHz）"),
        "filter_order": Option(default=4, type=int, help="BW 阶数"),
        "sg_window_size": Option(default=11, type=int, help="SG 窗口大小（奇数）"),
        "sg_poly_order": Option(default=2, type=int, help="SG 多项式阶数"),
        "daq_adapter": Option(
            default=None,
            type=str,
            help="DAQ 适配器名称（用于自动推断采样率）",
        ),
        # 你也可以加：sg_mode / sg_cval 等（这里先不扩展 options）
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> List[np.ndarray]:
        filter_type: str = context.get_config(self, "filter_type")
        if filter_type not in ("BW", "SG"):
            raise ValueError(f"不支持的滤波器类型: {filter_type}. 请使用 'BW' 或 'SG'.")

        bw_sos: Optional[np.ndarray] = None
        sg_window_size: Optional[int] = None
        sg_poly_order: Optional[int] = None

        if filter_type == "BW":
            lowcut = float(context.get_config(self, "lowcut"))
            highcut = float(context.get_config(self, "highcut"))
            fs = float(context.get_config(self, "fs"))
            daq_adapter = context.get_config(self, "daq_adapter")
            if not self._has_config(context, "fs"):
                fs = self._get_fs_from_adapter(daq_adapter, fs)
            order = int(context.get_config(self, "filter_order"))

            if fs <= 0:
                raise ValueError(f"fs ({fs}) 必须大于 0")
            if order <= 0:
                raise ValueError(f"滤波器阶数 ({order}) 必须大于 0")
            if lowcut <= 0 or highcut <= 0:
                raise ValueError("截止频率必须大于 0")
            if lowcut >= highcut:
                raise ValueError(f"lowcut ({lowcut}) 必须小于 highcut ({highcut})")
            if highcut >= fs / 2:
                raise ValueError(f"highcut ({highcut}) 必须小于奈奎斯特频率 ({fs / 2})")

            # SciPy: 直接用 fs 参数，避免手动归一化
            bw_sos = butter(order, [lowcut, highcut], btype="band", output="sos", fs=fs)
            logger.debug(
                "设计 Butterworth 带通滤波器: order=%s lowcut=%s highcut=%s fs=%s",
                order,
                lowcut,
                highcut,
                fs,
            )

        else:  # SG
            sg_window_size = int(context.get_config(self, "sg_window_size"))
            sg_poly_order = int(context.get_config(self, "sg_poly_order"))

            if sg_window_size <= 0:
                raise ValueError(f"SG 窗口大小 ({sg_window_size}) 必须大于 0")
            if sg_poly_order < 0:
                raise ValueError(f"SG 多项式阶数 ({sg_poly_order}) 必须大于等于 0")
            if sg_window_size % 2 == 0:
                sg_window_size += 1
                logger.warning("SG 窗口大小已调整为奇数: %s", sg_window_size)
            if sg_poly_order >= sg_window_size:
                raise ValueError(
                    f"SG 多项式阶数 ({sg_poly_order}) 必须小于窗口大小 ({sg_window_size})"
                )

            logger.debug(
                "SG 滤波器参数: window_size=%s poly_order=%s", sg_window_size, sg_poly_order
            )

        st_waveforms = context.get_data(run_id, "st_waveforms")
        filtered_waveforms_list: List[np.ndarray] = []

        for st_ch in st_waveforms:
            if len(st_ch) == 0:
                filtered_waveforms_list.append(np.array([], dtype=np.float32).reshape(0, 0))
                continue

            # (n_events, n_samples)
            # 用 float64 做滤波更稳（最后再 cast 回 float32）
            waveforms = np.stack(st_ch["wave"]).astype(np.float64, copy=False)

            if waveforms.ndim != 2 or waveforms.shape[0] == 0 or waveforms.shape[1] == 0:
                filtered_waveforms_list.append(np.array([], dtype=np.float32).reshape(0, 0))
                continue

            n_events, n_samples = waveforms.shape
            logger.debug("处理通道: n_events=%s n_samples=%s", n_events, n_samples)

            if filter_type == "BW":
                # 一次性对整块数据滤波（沿最后一维）
                filtered = sosfiltfilt(bw_sos, waveforms, axis=-1)

            else:
                # SG: 根据 n_samples 自适应窗口
                # 1) 不超过波形长度
                window = min(sg_window_size, n_samples)

                # 2) 必须为奇数
                if window % 2 == 0:
                    window -= 1  # 往下调，避免超过 n_samples

                # 3) 必须满足 window > poly_order
                if window <= sg_poly_order:
                    logger.warning(
                        "波形长度 (%s) 太短/窗口 (%s) 太小，无法 SG 滤波（需要 window > poly_order=%s），返回原波形",
                        n_samples,
                        window,
                        sg_poly_order,
                    )
                    filtered = waveforms
                else:
                    # mode='interp' 常用于避免边缘伪影（比默认更“保守”）
                    filtered = savgol_filter(
                        waveforms,
                        window_length=window,
                        polyorder=sg_poly_order,
                        axis=-1,
                        mode="interp",
                    )

            filtered_waveforms_list.append(filtered.astype(np.float32, copy=False))

        return filtered_waveforms_list

    def _has_config(self, context: Any, name: str) -> bool:
        config = getattr(context, "config", {})
        provides = self.provides
        if provides in config and isinstance(config[provides], dict):
            if name in config[provides]:
                return True
        if f"{provides}.{name}" in config:
            return True
        return name in config

    def _get_fs_from_adapter(self, daq_adapter: Optional[str], default_value: float) -> float:
        if not daq_adapter:
            return default_value
        try:
            from waveform_analysis.utils.formats import get_adapter
        except Exception:
            return default_value
        try:
            adapter = get_adapter(daq_adapter)
        except ValueError:
            return default_value
        sampling_rate_hz = adapter.sampling_rate_hz
        if not sampling_rate_hz:
            return default_value
        return float(sampling_rate_hz) / 1e9
