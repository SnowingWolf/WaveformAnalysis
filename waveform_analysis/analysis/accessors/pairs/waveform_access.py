"""S1-S2 waveform access methods."""

from ...s1_s2_pair_accessor import S1S2PairAccessor

waveform = S1S2PairAccessor.waveform
pair_waveforms = S1S2PairAccessor.pair_waveforms

__all__ = ["waveform", "pair_waveforms"]
