import numpy as np

# Strax-inspired dtypes for structured data
# Record: A single waveform with metadata
RECORD_DTYPE = [
    ("baseline", "f8"),  # float64 for baseline
    ("timestamp", "i8"),  # int64 for ps-level timestamps
    ("event_length", "i8"),  # length of the event
    ("wave", "O"),  # object for variable length waveform (or fixed if padded)
]

# Peak: A detected peak in a waveform
PEAK_DTYPE = [
    ("time", "i8"),  # time of the peak
    ("area", "f4"),  # area of the peak
    ("height", "f4"),  # height of the peak
    ("width", "f4"),  # width of the peak
    ("channel", "i2"),  # channel index
    ("event_index", "i8"),  # index of the event in the dataset
]


class WaveformStruct:
    def __init__(self, waveforms):
        self.waveforms = waveforms
        self.event_length = None
        self.waveform_structureds = None

    def _structure_waveform(self, waves=None):
        # If no explicit waves passed, use the first channel
        if waves is None:
            if not self.waveforms:
                return np.zeros(0, dtype=RECORD_DTYPE)
            waves = self.waveforms[0]

        # If waves is empty, return an empty structured array
        if len(waves) == 0:
            return np.zeros(0, dtype=RECORD_DTYPE)

        waveform_structured = np.zeros(len(waves), dtype=RECORD_DTYPE)

        # Safely compute baseline and timestamp
        try:
            baseline_vals = np.mean(waves[:, 7:47].astype(float), axis=1)
        except Exception:
            # Fallback: compute per-row mean for rows that have enough samples
            baselines = []
            for row in waves:
                try:
                    vals = np.asarray(row[7:], dtype=float)
                    if vals.size > 0:
                        baselines.append(np.mean(vals))
                    else:
                        baselines.append(np.nan)
                except Exception:
                    baselines.append(np.nan)
            baseline_vals = np.array(baselines, dtype=float)

        try:
            timestamps = waves[:, 2].astype(np.int64)
        except Exception:
            # Fallback: extract element 2 from each row
            timestamps = np.array([int(row[2]) for row in waves], dtype=np.int64)

        waveform_structured["baseline"] = baseline_vals
        waveform_structured["timestamp"] = timestamps
        waveform_structured["wave"] = [row[7:] for row in waves]
        return waveform_structured

    def structure_waveforms(self, show_progress: bool = False):
        if show_progress:
            try:
                from tqdm import tqdm

                pbar = tqdm(self.waveforms, desc="Structuring waveforms", leave=False)
            except ImportError:
                pbar = self.waveforms
        else:
            pbar = self.waveforms

        self.waveform_structureds = [self._structure_waveform(waves) for waves in pbar]
        return self.waveform_structureds

    def get_event_length(self):
        """Compute per-event lengths.

        Historically this computed "pair" lengths by taking the min of each adjacent
        pair of channels. We now generalize the concept to "event" lengths but keep
        the original behavior for backwards compatibility: adjacent channels are
        considered an event pair when computing the minimal length.
        """
        event_length = np.array([len(wave) for wave in self.waveforms])

        # 重塑为 (n_events, 2) 的形状进行处理（保留与历史配对行为一致）
        n = len(event_length)
        if n % 2 == 0:
            reshaped = event_length.reshape(-1, 2)
            min_vals = np.min(reshaped, axis=1)
            computed = np.repeat(min_vals, 2)
        else:
            reshaped = event_length[:-1].reshape(-1, 2)
            min_vals = np.min(reshaped, axis=1)
            computed = np.concatenate([np.repeat(min_vals, 2), [event_length[-1]]])

        self.event_length = computed
        return computed
