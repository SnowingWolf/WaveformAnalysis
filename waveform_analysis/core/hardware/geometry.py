"""PMT geometry and detector layout management.

This module provides PMT (Photomultiplier Tube) position mapping and gain calibration
for position reconstruction. It supports global configuration-based layout management.

Migrated and adapted from xihu_fast_analysis/layout.py.
"""

from dataclasses import dataclass
import json
from pathlib import Path

# Default PMT gain (ADC·ns / PE)
DEFAULT_PMT_GAIN = 9.2e6

# Fallback layout: 7 PMTs in hexagonal close-packed configuration
FALLBACK_ENTRIES = [
    {
        "pmt_no": 1,
        "pmt_id": "LV2389",
        "label": "Upper left",
        "x_mm": -26.8,
        "y_mm": 17.7,
        "board_id": 0,
        "channel_id": 15,
        "signal": "anode",
        "polarity": "negative",
    },
    {
        "pmt_no": 2,
        "pmt_id": "LV2387",
        "label": "Top",
        "x_mm": -1.9,
        "y_mm": 32.0,
        "board_id": 0,
        "channel_id": 14,
        "signal": "anode",
        "polarity": "negative",
    },
    {
        "pmt_no": 3,
        "pmt_id": "LV2380",
        "label": "Lower left",
        "x_mm": -24.9,
        "y_mm": -14.4,
        "board_id": 0,
        "channel_id": 13,
        "signal": "anode",
        "polarity": "negative",
    },
    {
        "pmt_no": 4,
        "pmt_id": "LV2332",
        "label": "Center",
        "x_mm": 0.0,
        "y_mm": 0.0,
        "board_id": 0,
        "channel_id": 12,
        "signal": "anode",
        "polarity": "negative",
    },
    {
        "pmt_no": 5,
        "pmt_id": "LV2391",
        "label": "Upper right",
        "x_mm": 24.9,
        "y_mm": 14.4,
        "board_id": 0,
        "channel_id": 11,
        "signal": "anode",
        "polarity": "negative",
    },
    {
        "pmt_no": 6,
        "pmt_id": "LV2364",
        "label": "Bottom",
        "x_mm": 1.9,
        "y_mm": -32.0,
        "board_id": 0,
        "channel_id": 10,
        "signal": "anode",
        "polarity": "negative",
    },
    {
        "pmt_no": 7,
        "pmt_id": "LV2319",
        "label": "Lower right",
        "x_mm": 26.8,
        "y_mm": -17.7,
        "board_id": 0,
        "channel_id": 9,
        "signal": "anode",
        "polarity": "negative",
    },
]

# Fast lookup tables
FALLBACK_BY_PMT_ID = {entry["pmt_id"]: entry for entry in FALLBACK_ENTRIES}
FALLBACK_BY_PMT_NO = {entry["pmt_no"]: entry for entry in FALLBACK_ENTRIES}


@dataclass(frozen=True)
class PmtEntry:
    """PMT channel physical and electronic mapping information.

    Attributes:
        pmt_no: Logical PMT number (1-indexed)
        pmt_id: PMT hardware serial number
        x_mm: X coordinate of PMT center (mm)
        y_mm: Y coordinate of PMT center (mm)
        board_id: DAQ board ID
        channel_id: DAQ channel ID
        signal: Signal type (e.g., "anode")
        polarity: Signal polarity ("negative" or "positive")
        label: Human-readable position label
        gain: PMT amplification gain (ADC·ns / PE)
    """

    pmt_no: int
    pmt_id: str
    x_mm: float
    y_mm: float
    board_id: int
    channel_id: int
    signal: str
    polarity: str
    label: str = ""
    gain: float = DEFAULT_PMT_GAIN

    @property
    def xy_mm(self) -> tuple[float, float]:
        """Return 2D position coordinates."""
        return (self.x_mm, self.y_mm)


@dataclass(frozen=True)
class PmtLayout:
    """Detector PMT physical geometry layout.

    Attributes:
        entries: Tuple of all PmtEntry objects
        source: Data source identifier ("config", "runinfo", or "fallback")
        run_id: Run number (if applicable)
        config_path: Configuration file path (if loaded from file)
    """

    entries: tuple[PmtEntry, ...]
    source: str
    run_id: str | None = None
    config_path: str | None = None

    def entry_for_pmt(self, pmt_no: int) -> PmtEntry:
        """Get PMT entry by logical PMT number.

        Args:
            pmt_no: PMT logical number

        Returns:
            PmtEntry object

        Raises:
            KeyError: If PMT number not found
        """
        pmt_no = int(pmt_no)
        for entry in self.entries:
            if entry.pmt_no == pmt_no:
                return entry
        raise KeyError(f"Unknown PMT number: {pmt_no}")

    def entry_for_readout(self, board_id: int, channel_id: int) -> PmtEntry:
        """Get PMT entry by hardware readout channel.

        Args:
            board_id: DAQ board ID
            channel_id: DAQ channel ID

        Returns:
            PmtEntry object

        Raises:
            KeyError: If readout channel not found
        """
        board_id = int(board_id)
        channel_id = int(channel_id)
        for entry in self.entries:
            if entry.board_id == board_id and entry.channel_id == channel_id:
                return entry
        raise KeyError(f"Unknown readout: board_id={board_id}, channel_id={channel_id}")

    def pmt_no_for(self, board_id: int, channel_id: int) -> int:
        """Get PMT number for hardware readout channel.

        Args:
            board_id: DAQ board ID
            channel_id: DAQ channel ID

        Returns:
            PMT logical number
        """
        return self.entry_for_readout(board_id, channel_id).pmt_no

    @property
    def channels_by_board(self) -> dict[tuple[int, int], PmtEntry]:
        """Return mapping from (board_id, channel_id) to PmtEntry."""
        return {(entry.board_id, entry.channel_id): entry for entry in self.entries}

    @property
    def pmt_positions(self) -> dict[int, tuple[float, float]]:
        """Return mapping from PMT number to (x_mm, y_mm) coordinates."""
        return {entry.pmt_no: entry.xy_mm for entry in self.entries}

    @property
    def gain_by_pmt(self) -> dict[int, float]:
        """Return mapping from PMT number to gain."""
        return {entry.pmt_no: float(entry.gain) for entry in self.entries}


def load_pmt_layout_from_config(
    config: dict, signal: str = "anode", default_gain: float = DEFAULT_PMT_GAIN
) -> PmtLayout | None:
    """Load PMT layout from configuration dictionary.

    Args:
        config: Configuration dictionary with 'detector_geometry' key
        signal: Signal type to filter (default: "anode")
        default_gain: Default gain if not specified in config

    Returns:
        PmtLayout object, or None if config is invalid

    Example config structure:
        {
            "detector_geometry": {
                "pmt_mapping": [
                    {
                        "board": 0,
                        "channel": 15,
                        "pmt_no": 1,
                        "pmt_id": "LV2389",
                        "x_mm": -26.8,
                        "y_mm": 17.7,
                        "gain": 9.2e6,
                        "label": "Upper left"
                    },
                    ...
                ]
            }
        }
    """
    detector_config = config.get("detector_geometry")
    if not detector_config:
        return None

    pmt_mapping = detector_config.get("pmt_mapping")
    if not pmt_mapping:
        return None

    global_default_gain = detector_config.get("default_gain", default_gain)

    entries = []
    for index, pmt_config in enumerate(pmt_mapping, start=1):
        # Get PMT identification
        pmt_no = pmt_config.get("pmt_no")
        if pmt_no is None:
            pmt_no = index
        pmt_no = int(pmt_no)

        pmt_id = pmt_config.get("pmt_id", pmt_config.get("pmt", ""))

        # Get position
        x_mm = float(pmt_config.get("x_mm", 0.0))
        y_mm = float(pmt_config.get("y_mm", 0.0))

        # Get hardware mapping
        board_id = int(pmt_config.get("board", pmt_config.get("board_id", 0)))
        channel_id = int(pmt_config.get("channel", pmt_config.get("channel_id", 0)))

        # Get gain (specific > global default)
        gain = float(pmt_config.get("gain", global_default_gain))

        # Get metadata
        label = pmt_config.get("label", "")
        sig = pmt_config.get("signal", signal)
        polarity = pmt_config.get("polarity", "negative")

        entries.append(
            PmtEntry(
                pmt_no=pmt_no,
                pmt_id=pmt_id,
                x_mm=x_mm,
                y_mm=y_mm,
                board_id=board_id,
                channel_id=channel_id,
                signal=sig,
                polarity=polarity,
                label=label,
                gain=gain,
            )
        )

    if not entries:
        return None

    return PmtLayout(
        entries=tuple(sorted(entries, key=lambda e: e.pmt_no)),
        source="config",
    )


def load_pmt_layout_from_runinfo(
    runinfo_path: Path, signal: str = "anode", default_gain: float = DEFAULT_PMT_GAIN
) -> PmtLayout | None:
    """Load PMT layout from runinfo.json file.

    Args:
        runinfo_path: Path to runinfo.json
        signal: Signal type to filter (default: "anode")
        default_gain: Default gain if not specified

    Returns:
        PmtLayout object, or None if file doesn't exist or is invalid

    Expected runinfo.json structure:
        {
            "run_info": {"run_id": "run_001"},
            "mapping": [{
                "board_id": 0,
                "signal": "anode",
                "polarity": "negative",
                "channels": [
                    {
                        "ch": 15,
                        "pmt": "LV2389",
                        "pmt_no": 1,
                        "pos": [-26.8, 17.7],
                        "gain": 9.2e6,
                        "label": "Upper left"
                    },
                    ...
                ]
            }]
        }
    """
    runinfo_path = Path(runinfo_path)
    if not runinfo_path.exists():
        return None

    try:
        payload = json.loads(runinfo_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    run_id = (payload.get("run_info") or {}).get("run_id")

    # Scan hardware mapping nodes
    for readout in payload.get("mapping", []) or []:
        if signal is not None and readout.get("signal") != signal:
            continue

        entries = []
        for index, channel in enumerate(readout.get("channels", []) or [], start=1):
            pmt_id = channel.get("pmt") or channel.get("pmt_id") or ""
            fallback = FALLBACK_BY_PMT_ID.get(pmt_id)

            pmt_no = channel.get("pmt_no")
            if pmt_no is None:
                pmt_no = fallback["pmt_no"] if fallback is not None else index
            pmt_no = int(pmt_no)

            pmt_fallback = FALLBACK_BY_PMT_NO.get(pmt_no, fallback or {})

            pos = channel.get("pos")
            if pos is None or len(pos) < 2:
                pos = [pmt_fallback.get("x_mm", 0.0), pmt_fallback.get("y_mm", 0.0)]

            # Get PMT-specific gain
            gain = _first_present(
                channel,
                readout,
                pmt_fallback,
                keys=("gain", "pmt_gain"),
                default=default_gain,
            )

            entries.append(
                PmtEntry(
                    pmt_no=pmt_no,
                    pmt_id=pmt_id or pmt_fallback.get("pmt_id", ""),
                    x_mm=float(pos[0]),
                    y_mm=float(pos[1]),
                    board_id=int(readout["board_id"]),
                    channel_id=int(channel["ch"]),
                    signal=readout.get("signal") or signal or "",
                    polarity=readout.get("polarity") or pmt_fallback.get("polarity", ""),
                    label=channel.get("label") or pmt_fallback.get("label", ""),
                    gain=float(gain),
                )
            )

        if entries:
            return PmtLayout(
                entries=tuple(sorted(entries, key=lambda entry: entry.pmt_no)),
                source="runinfo",
                run_id=run_id,
                config_path=str(runinfo_path),
            )

    return None


def load_fallback_layout(
    signal: str = "anode", default_gain: float = DEFAULT_PMT_GAIN
) -> PmtLayout:
    """Generate fallback PMT layout (7-PMT hexagonal configuration).

    Args:
        signal: Signal type to filter
        default_gain: Default gain for all PMTs

    Returns:
        PmtLayout object with fallback configuration
    """
    entries = []
    for item in FALLBACK_ENTRIES:
        if signal is not None and item["signal"] != signal:
            continue
        entries.append(PmtEntry(**item, gain=float(item.get("gain", default_gain))))
    return PmtLayout(entries=tuple(entries), source="fallback")


def _first_present(*sources, keys, default):
    """Helper: search for first non-None value across multiple sources.

    Args:
        *sources: Dictionaries to search
        keys: Keys to look for (tuple)
        default: Default value if not found

    Returns:
        First non-None value found, or default
    """
    for source in sources:
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
    return default
