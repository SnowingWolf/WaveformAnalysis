"""
数据加载测试
"""

import numpy as np
import pytest

from waveform_analysis.core import get_raw_files, get_waveforms


def test_raw_file_loader():
    """测试原始文件加载器"""
    from waveform_analysis.core.loader import RawFileLoader

    loader = RawFileLoader(n_channels=8, char="test")
    assert loader.n_channels == 8
    assert loader.base_dir.name == "RAW"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
