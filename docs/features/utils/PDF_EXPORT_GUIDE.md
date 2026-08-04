# Matplotlib PDF 导出

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [工具函数](README.md) > Matplotlib PDF 导出

`save_figures_pdf` 将一个或多个 Matplotlib `Figure` 导出为 PDF。单个 Figure 生成单页；多个 Figure 按输入顺序生成多页。

## 导入

```python
from waveform_analysis.utils import save_figures_pdf
```

也可从 `waveform_analysis.utils.visualization` 导入同名函数。

## 单页 PDF

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([0, 1, 4, 9])

pdf_path = save_figures_pdf(fig, "output/quadratic")
print(pdf_path)  # output/quadratic.pdf
```

## 多页 PDF

```python
figures = []
for channel in range(4):
    fig, ax = plt.subplots()
    ax.set_title(f"Channel {channel}")
    figures.append(fig)

save_figures_pdf(figures, "output/channel_report.pdf")
```

## 行为约定

- 参数 `figures` 接受单个 `Figure`，或 Figure 的列表、元组、生成器等可迭代对象。
- `output_path` 接受 `str` 或 `pathlib.Path`；函数会创建缺失的父目录，并把文件扩展名规范为 `.pdf`。
- 空 Figure 序列会抛出 `ValueError`；非 Figure 输入会抛出 `TypeError`。
- 函数不会关闭、展示或修改传入的 Figure；批量处理时由调用方自行调用 `plt.close()` 释放资源。
