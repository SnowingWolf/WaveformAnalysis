# DAQ 格式与适配器

公共契约和注册入口放在本层，设备实现按设备集中管理：

```text
formats/
├── adapter.py       # DAQAdapter 和适配器注册
├── base.py          # 格式规范、时间戳单位、读取器接口
├── directory.py     # 公共目录布局
├── generic.py       # 通用 CSV 读取器
├── registry.py      # 格式注册
├── v1725/
│   ├── __init__.py  # V1725 公共导出
│   ├── reader.py    # DAW_DEMO 格式、布局、读取器和适配器
│   └── numba.py     # V1725 专属加速函数
└── vx2730/
    ├── __init__.py  # VX2730 CSV 和 BIN 公共导出
    ├── csv.py       # CSV 格式、布局、读取器和适配器
    └── binary.py    # CoMPASS BIN 格式、布局、读取器和适配器
```

通常通过 `waveform_analysis.acquisition.formats.get_adapter()` 获取适配器。
设备公共类仍可从 `formats.v1725` 和 `formats.vx2730` 导入。
本层的 `v1725_numba.py` 和 `vx2730_bin.py` 仅保留旧导入兼容，分别指向
`v1725.numba` 和 `vx2730.binary` 的同一个模块对象；新实现应使用设备包路径。
`waveform_analysis.utils.formats` 及其子模块同样保留别名，既有类的序列化路径不变。
