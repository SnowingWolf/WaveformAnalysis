"""
DataFrame Plugin - DataFrame 构建插件

**加速器**: CPU (NumPy/Pandas)
**功能**: 构建单通道事件的 DataFrame

本模块包含 DataFrame 构建插件，整合结构化波形与基础特征，
构建包含所有事件信息的 pandas DataFrame。
"""

import logging
from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin

logger = logging.getLogger(__name__)


class DataFramePlugin(Plugin):
    """Plugin to build the initial single-channel events DataFrame."""

    provides = "df"
    depends_on = ["st_waveforms", "basic_features"]
    version = "1.4.0"
    save_when = "always"
    options = {
        "gain_adc_per_pe": Option(
            default=None,
            type=dict,
            help=(
                "按通道配置 ADC/PE 增益，如 {0: 12.5, 1: 13.2}。"
                "设置后会新增 area_pe/height_pe 列。"
            ),
        )
    }

    @staticmethod
    def _normalize_gain_map(gain_adc_per_pe: Any) -> dict:
        """
        标准化并校验增益映射。

        Returns:
            dict: {channel(int): gain(float)}，仅包含有效的正增益。
        """
        if not isinstance(gain_adc_per_pe, dict):
            return {}

        gain_map = {}
        for channel, gain in gain_adc_per_pe.items():
            try:
                channel_int = int(channel)
                gain_float = float(gain)
            except (TypeError, ValueError):
                logger.warning(
                    "df.gain_adc_per_pe has invalid entry: channel=%r, gain=%r", channel, gain
                )
                continue
            if gain_float <= 0:
                logger.warning(
                    "df.gain_adc_per_pe[%s]=%s is non-positive; calibrated columns will be NaN for this channel",
                    channel_int,
                    gain_float,
                )
                continue
            gain_map[channel_int] = gain_float
        return gain_map

    @staticmethod
    def _extract_gain_from_run_config(run_config: Any) -> Any:
        """Extract gain map from run-level config."""
        if not isinstance(run_config, dict):
            return None

        calibration = run_config.get("calibration")
        if isinstance(calibration, dict) and isinstance(calibration.get("gain_adc_per_pe"), dict):
            return calibration.get("gain_adc_per_pe")

        # Backward-compatible fallback.
        if isinstance(run_config.get("gain_adc_per_pe"), dict):
            return run_config.get("gain_adc_per_pe")

        return None

    def _resolve_gain_map(self, context: Any, run_id: str) -> tuple[dict, bool]:
        """
        Resolve gain map with precedence:
        explicit config > run_config.json > none.

        Returns:
            (normalized_gain_map, enabled)
            enabled=True means calibrated columns should be emitted.
        """
        gain_adc_per_pe = context.get_config(self, "gain_adc_per_pe")

        explicit_config = False
        has_explicit = getattr(context, "has_explicit_config", None)
        if callable(has_explicit):
            try:
                explicit_config = bool(has_explicit(self, "gain_adc_per_pe"))
            except Exception:
                explicit_config = False

        if explicit_config:
            if isinstance(gain_adc_per_pe, dict):
                return self._normalize_gain_map(gain_adc_per_pe), bool(gain_adc_per_pe)
            return {}, False

        if isinstance(gain_adc_per_pe, dict) and gain_adc_per_pe:
            return self._normalize_gain_map(gain_adc_per_pe), True

        run_config_getter = getattr(context, "get_run_config", None)
        if callable(run_config_getter):
            try:
                run_config = run_config_getter(run_id)
                run_gain = self._extract_gain_from_run_config(run_config)
                if isinstance(run_gain, dict):
                    return self._normalize_gain_map(run_gain), bool(run_gain)
            except Exception as exc:
                logger.warning(
                    "Failed to resolve gain from run config for run '%s': %s", run_id, exc
                )

        return {}, False

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        构建单通道事件的 DataFrame

        整合结构化波形与 height/area 特征，构建包含所有事件信息的 pandas DataFrame。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms, basic_features

        Returns:
            pd.DataFrame: 包含所有通道事件的 DataFrame

        Examples:
            >>> df = ctx.get_data('run_001', 'df')
            >>> print(f"总事件数: {len(df)}")
        """
        import pandas as pd

        st_waveforms = context.get_data(run_id, "st_waveforms")
        basic_features = context.get_data(run_id, "basic_features")

        if not isinstance(st_waveforms, np.ndarray):
            raise ValueError("df expects st_waveforms as a single structured array")
        if not isinstance(basic_features, np.ndarray):
            raise ValueError("df expects basic_features as a single structured array")

        if len(st_waveforms) != len(basic_features):
            raise ValueError(
                f"basic_features length ({len(basic_features)}) != st_waveforms length ({len(st_waveforms)})"
            )

        df = pd.DataFrame(
            {
                "timestamp": np.asarray(st_waveforms["timestamp"]),
                "area": np.asarray(basic_features["area"]),
                "height": np.asarray(basic_features["height"]),
                "amp": np.asarray(basic_features["amp"]),
                "board": (
                    np.asarray(st_waveforms["board"])
                    if "board" in st_waveforms.dtype.names
                    else np.zeros(len(st_waveforms), dtype=np.int16)
                ),
                "channel": np.asarray(st_waveforms["channel"]),
            }
        )

        gain_map, enable_calibrated_columns = self._resolve_gain_map(context, run_id)
        if enable_calibrated_columns:
            channels = df["channel"].to_numpy()
            gains = np.full(len(df), np.nan, dtype=np.float64)
            for channel, gain in gain_map.items():
                gains[channels == channel] = gain
            df["area_pe"] = np.asarray(df["area"], dtype=np.float64) / gains
            df["height_pe"] = np.asarray(df["height"], dtype=np.float64) / gains

        return df.sort_values("timestamp")
