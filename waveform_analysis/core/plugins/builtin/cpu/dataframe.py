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

from waveform_analysis.core.hardware.channel import (
    get_gain_adc_per_pe,
    resolve_channel_value_map,
    unique_hardware_channels,
)
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    WAVE_SOURCE_AUTO,
    WAVE_SOURCE_FILTERED,
    WAVE_SOURCE_RECORDS,
    resolve_wave_source,
)
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    resolve_depends_on as resolve_wave_depends_on,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin

logger = logging.getLogger(__name__)


class DataFramePlugin(Plugin):
    """Plugin to build the initial single-channel events DataFrame."""

    provides = "df"
    depends_on = []  # dynamic, resolved by resolve_depends_on
    description = "Build the initial single-channel events DataFrame."
    version = "1.7.0"
    save_when = "always"
    uses_run_config = True
    options = {
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin）",
        ),
        "wave_source": Option(
            default=WAVE_SOURCE_AUTO,
            type=str,
            help="波形数据源: auto|records|st_waveforms|filtered_waveforms",
        ),
        "gain_adc_per_pe": Option(
            default=None,
            type=dict,
            help=(
                '按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，'
                '例如 {"0:0": 12.5, "0:1": 13.2}。'
                "设置后会新增 area_pe/height_pe 列。"
            ),
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        source = resolve_wave_source(context, self)
        use_filtered = bool(context.get_config(self, "use_filtered"))
        # Dynamic dependency: df follows the selected waveform source, and
        # always adds basic_features as an extra upstream table dependency.
        deps = resolve_wave_depends_on(source, use_filtered)
        deps.append("basic_features")
        return deps

    @staticmethod
    def _resolve_basic_features_source(context: Any) -> str:
        # Keep df and basic_features source selection aligned in records mode.
        from waveform_analysis.core.plugins.builtin.cpu.basic_features import BasicFeaturesPlugin

        return resolve_wave_source(context, BasicFeaturesPlugin())

    @staticmethod
    def _normalize_gain_map(gain_adc_per_pe: Any) -> dict:
        """
        标准化增益映射原始结构。

        Returns:
            dict: dict-like gain config.
        """
        if not isinstance(gain_adc_per_pe, dict):
            return {}
        for channel, gain in gain_adc_per_pe.items():
            try:
                gain_float = float(gain)
            except (TypeError, ValueError):
                logger.warning(
                    "df.gain_adc_per_pe has invalid entry: channel=%r, gain=%r", channel, gain
                )
                continue
            if gain_float <= 0:
                logger.warning(
                    "df.gain_adc_per_pe[%s]=%s is non-positive; calibrated columns will be NaN for this channel",
                    channel,
                    gain_float,
                )
        return dict(gain_adc_per_pe)

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

    def _resolve_gain_map(
        self,
        context: Any,
        run_id: str,
        hardware_channels: list,
    ) -> tuple[dict, bool]:
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
                return (
                    resolve_channel_value_map(
                        channel_config=self._normalize_gain_map(gain_adc_per_pe),
                        run_id=run_id,
                        channels=hardware_channels,
                        plugin_name=self.provides,
                        value_name="gain_adc_per_pe",
                    ),
                    bool(gain_adc_per_pe),
                )
            return {}, False

        if isinstance(gain_adc_per_pe, dict) and gain_adc_per_pe:
            return (
                resolve_channel_value_map(
                    channel_config=self._normalize_gain_map(gain_adc_per_pe),
                    run_id=run_id,
                    channels=hardware_channels,
                    plugin_name=self.provides,
                    value_name="gain_adc_per_pe",
                ),
                True,
            )

        run_config_getter = getattr(context, "get_run_config", None)
        if callable(run_config_getter):
            try:
                run_config = run_config_getter(run_id)
                run_gain = self._extract_gain_from_run_config(run_config)
                if isinstance(run_gain, dict):
                    return (
                        resolve_channel_value_map(
                            channel_config=self._normalize_gain_map(run_gain),
                            run_id=run_id,
                            channels=hardware_channels,
                            plugin_name=self.provides,
                            value_name="gain_adc_per_pe",
                        ),
                        bool(run_gain),
                    )
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

        source = resolve_wave_source(context, self)
        use_filtered = bool(context.get_config(self, "use_filtered"))
        basic_features = context.get_data(run_id, "basic_features")

        if not isinstance(basic_features, np.ndarray):
            raise ValueError("df expects basic_features as a single structured array")

        if source == WAVE_SOURCE_RECORDS:
            basic_source = self._resolve_basic_features_source(context)
            if basic_source != WAVE_SOURCE_RECORDS:
                raise ValueError(
                    "df.wave_source=records requires basic_features.wave_source=records "
                    f"(resolved as {basic_source!r})."
                )

            from waveform_analysis.core import records_view

            rv = records_view(context, run_id)
            records = rv.records

            if len(records) != len(basic_features):
                raise ValueError(
                    f"basic_features length ({len(basic_features)}) != records length ({len(records)})"
                )

            df = pd.DataFrame(
                {
                    "timestamp": np.asarray(records["timestamp"]),
                    "record_id": (
                        np.asarray(records["record_id"], dtype=np.int64)
                        if "record_id" in records.dtype.names
                        else np.arange(len(records), dtype=np.int64)
                    ),
                    "area": np.asarray(basic_features["area"]),
                    "height": np.asarray(basic_features["height"]),
                    "amp": np.asarray(basic_features["amp"]),
                    "board": (
                        np.asarray(records["board"])
                        if "board" in records.dtype.names
                        else np.zeros(len(records), dtype=np.int16)
                    ),
                    "channel": (
                        np.asarray(records["channel"])
                        if "channel" in records.dtype.names
                        else np.zeros(len(records), dtype=np.int16)
                    ),
                }
            )
        else:
            if source == WAVE_SOURCE_FILTERED or (source == WAVE_SOURCE_AUTO and use_filtered):
                waveform_data = context.get_data(run_id, "filtered_waveforms")
                expected_name = "filtered_waveforms"
            else:
                waveform_data = context.get_data(run_id, "st_waveforms")
                expected_name = "st_waveforms"

            if not isinstance(waveform_data, np.ndarray):
                raise ValueError(f"df expects {expected_name} as a single structured array")

            if len(waveform_data) != len(basic_features):
                raise ValueError(
                    f"basic_features length ({len(basic_features)}) != "
                    f"{expected_name} length ({len(waveform_data)})"
                )

            df = pd.DataFrame(
                {
                    "timestamp": np.asarray(waveform_data["timestamp"]),
                    "record_id": (
                        np.asarray(waveform_data["record_id"], dtype=np.int64)
                        if "record_id" in waveform_data.dtype.names
                        else np.arange(len(waveform_data), dtype=np.int64)
                    ),
                    "area": np.asarray(basic_features["area"]),
                    "height": np.asarray(basic_features["height"]),
                    "amp": np.asarray(basic_features["amp"]),
                    "board": (
                        np.asarray(waveform_data["board"])
                        if "board" in waveform_data.dtype.names
                        else np.zeros(len(waveform_data), dtype=np.int16)
                    ),
                    "channel": np.asarray(waveform_data["channel"]),
                }
            )

        hardware_channels = unique_hardware_channels(
            df["board"].to_numpy(),
            df["channel"].to_numpy(),
        )
        gain_map, enable_calibrated_columns = self._resolve_gain_map(
            context,
            run_id,
            hardware_channels,
        )
        if enable_calibrated_columns:
            channels = df["channel"].to_numpy()
            boards = df["board"].to_numpy()
            gains = np.full(len(df), np.nan, dtype=np.float64)
            for idx in range(len(df)):
                gain = get_gain_adc_per_pe(gain_map, int(boards[idx]), int(channels[idx]))
                if gain is not None:
                    gains[idx] = gain
            df["area_pe"] = np.asarray(df["area"], dtype=np.float64) / gains
            df["height_pe"] = np.asarray(df["height"], dtype=np.float64) / gains

        return df.sort_values("timestamp")
