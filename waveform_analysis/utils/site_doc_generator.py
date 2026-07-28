"""Internal generator for the offline WaveformAnalysis documentation site."""

from dataclasses import dataclass
import inspect
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any
from xml.etree import ElementTree

from markupsafe import Markup, escape
import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor
from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator
from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor
from waveform_analysis.utils.visualization.statistical_plots import (
    corner_hist,
    plot_1d_cut_on_corner,
    plot_2d_cut_on_corner,
)
from waveform_analysis.utils.visualization.waveform_visualizer import (
    create_peak_plotter,
    plot_peak_channels_with_sum,
    plot_waveforms,
)

_CONTENT_BLOCK_KINDS = frozenset(
    {"heading", "paragraph", "list", "note", "code", "image", "mathml", "table"}
)
_MATHML_TAGS = frozenset(
    {
        "math",
        "mrow",
        "mi",
        "mn",
        "mo",
        "mtext",
        "ms",
        "mspace",
        "mstyle",
        "merror",
        "mpadded",
        "mphantom",
        "mfenced",
        "menclose",
        "msub",
        "msup",
        "msubsup",
        "munder",
        "mover",
        "munderover",
        "mmultiscripts",
        "mtable",
        "mtr",
        "mtd",
        "maligngroup",
        "malignmark",
        "mlabeledtr",
        "mfrac",
        "msqrt",
        "mroot",
        "mstack",
        "mlongdiv",
        "mscarries",
        "mscarry",
        "msline",
        "maction",
        "semantics",
        "annotation",
        "annotation-xml",
    }
)
_MATHML_ATTRIBUTES = frozenset(
    {
        "xmlns",
        "display",
        "mathvariant",
        "mathsize",
        "mathcolor",
        "mathbackground",
        "scriptlevel",
        "displaystyle",
        "accent",
        "accentunder",
        "stretchy",
        "symmetric",
        "form",
        "fence",
        "separator",
        "lspace",
        "rspace",
        "minsize",
        "maxsize",
        "movablelimits",
        "largeop",
        "linebreak",
        "depth",
        "height",
        "width",
        "voffset",
        "linethickness",
        "numalign",
        "denomalign",
        "bevelled",
        "open",
        "close",
        "separators",
        "notation",
        "columnalign",
        "rowalign",
        "columnspacing",
        "rowspacing",
        "columnlines",
        "rowlines",
        "frame",
        "framespacing",
        "equalcolumns",
        "equalrows",
        "columnspan",
        "rowspan",
        "groupalign",
        "align",
        "charalign",
        "charspacing",
        "side",
        "minlabelspacing",
        "selection",
        "actiontype",
        "encoding",
    }
)


def _safe_mathml(value: str) -> Markup:
    """Validate a small, presentation-only MathML subset before marking it safe."""
    if "<!" in value or "<?" in value:
        raise ValueError("MathML must not contain declarations or processing instructions")
    try:
        root = ElementTree.fromstring(value)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid MathML content block") from exc

    if root.tag.rsplit("}", maxsplit=1)[-1] != "math":
        raise ValueError("A MathML content block must have a <math> root element")
    for element in root.iter():
        tag = element.tag.rsplit("}", maxsplit=1)[-1]
        if tag not in _MATHML_TAGS:
            raise ValueError(f"Unsupported MathML element: {tag}")
        for attribute in element.attrib:
            attribute_name = attribute.rsplit("}", maxsplit=1)[-1]
            if attribute_name not in _MATHML_ATTRIBUTES:
                raise ValueError(f"Unsupported MathML attribute: {attribute_name}")
    return Markup(ElementTree.tostring(root, encoding="unicode", method="xml"))


@dataclass(frozen=True)
class DocumentationContentBlock:
    """A controlled, offline-safe documentation element rendered by a web template."""

    kind: str
    text: str = ""
    items: tuple[str, ...] = ()
    ordered: bool = False
    heading_level: int = 3
    title: str = ""
    tone: str = "note"
    code: str = ""
    language: str = "text"
    image_src: str = ""
    image_alt: str = ""
    image_caption: str = ""
    mathml: str = ""
    table_headers: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in _CONTENT_BLOCK_KINDS:
            raise ValueError(f"Unsupported documentation content block: {self.kind}")
        if self.kind == "heading":
            if not self.text:
                raise ValueError("A heading content block requires text")
            if self.heading_level not in {3, 4}:
                raise ValueError("A heading content block must use level 3 or 4")
        if self.kind == "paragraph" and not self.text:
            raise ValueError("A paragraph content block requires text")
        if self.kind == "list" and not self.items:
            raise ValueError("A list content block requires items")
        if self.kind == "note":
            if not self.text:
                raise ValueError("A note content block requires text")
            if self.tone not in {"note", "important", "warning"}:
                raise ValueError(f"Unsupported note tone: {self.tone}")
        if self.kind == "code" and not self.code:
            raise ValueError("A code content block requires source code")
        if self.kind == "image":
            if not self.image_src or not self.image_alt:
                raise ValueError("An image content block requires image_src and image_alt")
            path = PurePosixPath(self.image_src)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("image_src must be a relative path inside content-assets")
        if self.kind == "mathml":
            if not self.mathml:
                raise ValueError("A MathML content block requires mathml")
            _safe_mathml(self.mathml)
        if self.kind == "table":
            if not self.table_headers:
                raise ValueError("A table content block requires table_headers")
            if any(len(row) != len(self.table_headers) for row in self.table_rows):
                raise ValueError("Every table content block row must match its header width")


@dataclass(frozen=True)
class AccessorMemberSpec:
    name: str
    description: str
    kind: str = "method"
    parameters: tuple["AccessorParameterSpec", ...] = ()
    returns: str = ""
    notes: tuple[str, ...] = ()
    example: str = ""


@dataclass(frozen=True)
class AccessorParameterSpec:
    name: str
    description: str


@dataclass(frozen=True)
class AccessorNarrativeSection:
    """One curated explanatory section rendered before an Accessor API list."""

    anchor: str
    title: str
    blocks: tuple[DocumentationContentBlock, ...]


@dataclass(frozen=True)
class AccessorDocumentationSpec:
    accessor_class: type
    slug: str
    summary: str
    introduction: str
    purpose: str
    example: str
    constructor_parameters: tuple[AccessorParameterSpec, ...]
    members: tuple[AccessorMemberSpec, ...]
    narrative_sections: tuple[AccessorNarrativeSection, ...] = ()
    overview_title: str = "整体介绍"
    overview_blocks: tuple[DocumentationContentBlock, ...] = ()


@dataclass(frozen=True)
class AccessorMemberView:
    name: str
    kind: str
    signature: str
    signature_html: Markup
    description: str
    parameters: tuple[AccessorParameterSpec, ...]
    returns: str
    notes: tuple[str, ...]
    example_html: Markup


@dataclass(frozen=True)
class AccessorDocumentationView:
    name: str
    slug: str
    module_path: str
    summary: str
    introduction: str
    purpose: str
    example_html: Markup
    constructor_signature: str
    constructor_parameters: tuple[AccessorParameterSpec, ...]
    members: tuple[AccessorMemberView, ...]
    narrative_sections: tuple[AccessorNarrativeSection, ...] = ()
    overview_title: str = "整体介绍"
    overview_blocks: tuple[DocumentationContentBlock, ...] = ()


@dataclass(frozen=True)
class CallableDocumentationSpec:
    name: str
    callable: Any
    description: str
    parameters: tuple[AccessorParameterSpec, ...] = ()
    returns: str = ""
    notes: tuple[str, ...] = ()
    example: str = ""
    kind: str = "function"


@dataclass(frozen=True)
class CallableDocumentationGroup:
    anchor: str
    title: str
    description: str
    members: tuple[CallableDocumentationSpec, ...]


@dataclass(frozen=True)
class CallableDocumentationPageSpec:
    slug: str
    title: str
    eyebrow: str
    summary: str
    introduction: str
    groups: tuple[CallableDocumentationGroup, ...]


@dataclass(frozen=True)
class CallableDocumentationView:
    name: str
    signature_html: Markup
    description: str
    parameters: tuple[AccessorParameterSpec, ...]
    returns: str
    notes: tuple[str, ...]
    example_html: Markup
    kind: str


@dataclass(frozen=True)
class CallableDocumentationPageView:
    slug: str
    title: str
    eyebrow: str
    summary: str
    introduction: str
    groups: tuple[tuple[CallableDocumentationGroup, tuple[CallableDocumentationView, ...]], ...]


ACCESSOR_DOCUMENTATION_REGISTRY = (
    AccessorDocumentationSpec(
        accessor_class=PeakChannelAccessor,
        slug="peak-channel-accessor",
        summary="通过 peaks 对应的分通道信息查询硬件通道特征与波形，并提供常用对比绘图。",
        introduction=(
            "PeakChannelAccessor 面向单个 peak 的通道级排查。它先读取轻量的特征层，"
            "只有请求波形或绘图时才读取 records 与 wave pool，因此适合先用面积和高度筛选，"
            "再针对少量候选做波形检查。"
        ),
        purpose=(
            "返回通道唯一键 `(board, channel)` 下的聚合特征；当 `peaklet_channels` 可用时，"
            "其中的 `area`、`height`、`n_hits` 与 `area_fraction` 是每通道聚合值。"
        ),
        overview_title="整体介绍",
        overview_blocks=(
            DocumentationContentBlock(
                kind="paragraph",
                text=(
                    "`PeakChannelAccessor` 用于排查单个 peak 的通道级组成。它以 `(board, channel)` "
                    "作为逻辑通道的唯一标识，提供每个通道的聚合特征，并支持按需读取对应波形。"
                ),
            ),
            DocumentationContentBlock(
                kind="paragraph",
                text="其推荐使用方式是：",
            ),
            DocumentationContentBlock(
                kind="list",
                ordered=True,
                items=(
                    "先读取轻量特征；",
                    "根据面积、高度或面积占比筛选通道；",
                    "仅对少量候选通道加载和检查波形。",
                ),
            ),
            DocumentationContentBlock(
                kind="paragraph",
                text="这种设计避免了为全部 peak 和通道预先读取、切片体积较大的 `wave_pool`。",
            ),
        ),
        narrative_sections=(
            AccessorNarrativeSection(
                anchor="typical-applications",
                title="典型应用",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph", text="`PeakChannelAccessor` 主要适用于以下任务："
                    ),
                    DocumentationContentBlock(
                        kind="list",
                        items=(
                            "找出单个 peak 中面积或高度贡献最大的通道；",
                            "根据 `area_fraction` 判断信号在不同通道之间的分布；",
                            "排查异常通道、异常 hit 或波形形状；",
                            "比较多个候选通道的时间结构；",
                            "对照框架生成的 peak 求和波形与通道波形叠加结果。",
                        ),
                    ),
                ),
            ),
            AccessorNarrativeSection(
                anchor="channel-identification",
                title="字段来源与计算口径",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "通道必须使用 `(board, channel)` 作为唯一键。不能只使用 `channel`，"
                            "因为不同采集板上可能存在编号相同的通道。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text="`peaklet_channels` 是唯一的通道聚合真源；缺失或字段不完整时 Accessor 会失败，不会退回到部分字段的字典。",
                    ),
                    DocumentationContentBlock(
                        kind="table",
                        table_headers=("字段", "含义", "计算口径"),
                        table_rows=(
                            ("`board`", "采集板编号", "通道标识"),
                            ("`channel`", "板内通道编号", "通道标识"),
                            (
                                "`area`",
                                "通道面积",
                                "同一 (peaklet_id, board, channel) 的有效组件 area 之和",
                            ),
                            ("`height`", "通道高度", "同一分组内有效组件 height 的最大值"),
                            ("`n_hits`", "通道 hit 数", "同一分组内有效组件 n_hits 之和"),
                            (
                                "`area_fraction`",
                                "通道面积占比",
                                "area / peaklet_features.area；分母为 0 时为 0",
                            ),
                            (
                                "`merged_indices`",
                                "通道组件索引",
                                "来自 peaklet_components 的全部 merged_index",
                            ),
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="heading", text="代表组件与边界字段", heading_level=3
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text="`width`、`rise_time`、`fall_time`、`center_time` 与 `record_id` 来自高度最大的组件；`merged_index` 也指向该代表组件。",
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "`sample_start` 与 `sample_end` 分别是所有组件的最小起点和最大终点；"
                            "`is_single_record` 仅在全部组件均为单 record 时为真。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="list",
                        items=(
                            "聚合前先过滤 hit_merged_features.valid == 0 的特征；",
                            "面积、高度和 hit 数描述整个逻辑通道，时间字段只描述代表组件；",
                            "通道波形来自 records + wave_pool，求和波形来自 peaklet_waveforms + peaklet_waveform_pool。",
                        ),
                    ),
                ),
            ),
            AccessorNarrativeSection(
                anchor="data-loading",
                title="数据层与加载策略",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph",
                        text="Accessor 将数据访问分为特征层和波形层。",
                    ),
                    DocumentationContentBlock(
                        kind="table",
                        table_headers=("数据层", "主要依赖", "加载时机"),
                        table_rows=(
                            (
                                "特征层",
                                "`peaklet_components`、`peaklet_channels`、`hit_merged`、`hit_merged_features`",
                                "查询通道特征时",
                            ),
                            (
                                "波形层",
                                "`records`、`hit_threshold`、`hit_merged_components`、`wave_pool`",
                                "请求波形或绘图时",
                            ),
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "调用 `get_channels()` 时只访问特征层，不读取通道波形。只有在 `include_waveforms=True` 或"
                            "调用相关绘图方法时，Accessor 才会加载波形层。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text="这意味着可以先对大量 peak 执行轻量特征查询，再对少量候选加载波形。",
                    ),
                ),
            ),
            AccessorNarrativeSection(
                anchor="waveform-semantics",
                title="波形来源与语义",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph", text="Accessor 中存在两类来源不同的波形。"
                    ),
                    DocumentationContentBlock(
                        kind="table",
                        table_headers=("波形类型", "获取方式", "数据来源"),
                        table_rows=(
                            (
                                "Peak 求和波形",
                                "`get_sum_waveform()`",
                                "`peaklet_waveforms` 生成的求和产物",
                            ),
                            (
                                "通道或组件波形",
                                "通道波形接口",
                                "根据 hit 窗口和 `pad` 从 `records + wave_pool` 提取",
                            ),
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "两类波形的构建路径不同，因此不要求逐采样点完全一致。可能造成差异的因素包括："
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="list",
                        items=(
                            "使用的时间网格不同；",
                            "`wave_pool` 中保存的是经过处理的波形；",
                            "波形窗口及 `pad` 配置不同；",
                            "peak 求和波形与通道波形采用了不同的构建配置。",
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="note",
                        tone="important",
                        title="使用 `plot(view='sum-comparison')` 时",
                        text="应将其理解为对两种波形构建结果的对照，而不是逐点相等性检验。",
                    ),
                ),
            ),
            AccessorNarrativeSection(
                anchor="lazy-loading-and-cache",
                title="延迟加载与缓存",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph",
                        text="建议在同一个分析循环中复用同一个 `PeakChannelAccessor`，避免重复初始化和读取相同数据。",
                    ),
                    DocumentationContentBlock(kind="paragraph", text="设置："),
                    DocumentationContentBlock(
                        kind="code", language="python", code="lazy_load=True"
                    ),
                    DocumentationContentBlock(
                        kind="paragraph", text="可以推迟首次特征层读取，直到真正执行查询。"
                    ),
                    DocumentationContentBlock(kind="paragraph", text="波形窗口按照："),
                    DocumentationContentBlock(
                        kind="code", language="text", code="(merged_index, pad)"
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text="进行缓存。使用相同参数再次请求波形时，可以复用已经提取的结果。",
                    ),
                    DocumentationContentBlock(kind="paragraph", text="当内存紧张时，可以调用："),
                    DocumentationContentBlock(
                        kind="code",
                        language="python",
                        code="clear_waveform_cache(release_wave_pool=True)",
                    ),
                    DocumentationContentBlock(kind="paragraph", text="该操作会："),
                    DocumentationContentBlock(
                        kind="list",
                        items=(
                            "清除已缓存的波形窗口；",
                            "在 `release_wave_pool=True` 时释放波形层；",
                            "保留 Accessor，使其仍可继续使用。",
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text="清理后再次请求波形时，Accessor 会重新加载所需的波形数据。",
                    ),
                ),
            ),
        ),
        example="""from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(ctx, run_id="run_001", lazy_load=True)
channels = accessor.get_channels(peak_id=919)""",
        constructor_parameters=(
            AccessorParameterSpec("context", "已配置插件和数据存储的 Context。"),
            AccessorParameterSpec("run_id", "本次查询对应的 run ID，所有访问都显式绑定到该 run。"),
            AccessorParameterSpec(
                "lazy_load", "为 `True` 时延迟读取特征层；适合先创建多个访问器但不立即查询的场景。"
            ),
        ),
        members=(
            AccessorMemberSpec(
                "get_channels",
                "返回一个 peak 的逐逻辑通道特征；设置 include_waveforms=True 时，为每项附加完整逻辑通道波形。",
                parameters=(
                    AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),
                    AccessorParameterSpec("include_waveforms", "为 True 时加载并附加波形字段。"),
                    AccessorParameterSpec("pad", "波形窗口两侧额外保留的采样点数。"),
                ),
                returns=(
                    "`list[dict]`；每项始终包含完整规范特征字段。启用波形后额外包含 "
                    "`waveform`、`time_ns`、`abs_time_ps`、`dt` 和 `segments`。"
                ),
                notes=(
                    "空 peak 返回空列表。",
                    "通道键始终按 `(board, channel)` 解释。",
                    "缺少或不完整的 `peaklet_channels` 会抛出 `PeakChannelDataUnavailableError`，不会使用 fallback。",
                    "一个逻辑通道的全部 `merged_indices` 会按绝对时间合并为波形片段。",
                ),
                example="""channels = accessor.get_channels(peak_id=919, include_waveforms=True)
for channel in channels:
    print(channel["board"], channel["channel"], channel["area"])
""",
            ),
            AccessorMemberSpec(
                "get_sum_waveform",
                "取得框架已有的 peak 求和波形及其时间信息。",
                parameters=(AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),),
                returns="求和波形字典；找不到对应 peak 时返回 `None`。",
                notes=(
                    "来源是 `peaklet_waveforms` 与 `peaklet_waveform_pool`，不会从当前通道曲线重新求和。",
                    "与通道波形的窗口、时间网格和滤波来源可能不同，因此不保证逐点相同。",
                ),
            ),
            AccessorMemberSpec(
                "clear_waveform_cache",
                "清空已提取的通道波形缓存，可选地释放原始波形层。",
                parameters=(
                    AccessorParameterSpec(
                        "release_wave_pool", "为 True 时同时释放已加载的 records/wave pool 层。"
                    ),
                ),
                returns="无返回值。",
            ),
            AccessorMemberSpec(
                "plot",
                "唯一的绘图入口：通过 view 选择逐通道总览、通道叠加或求和对照。",
                parameters=(
                    AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),
                    AccessorParameterSpec("view", "`stacked`、`overlay` 或 `sum-comparison`。"),
                    AccessorParameterSpec("pad", "通道波形窗口的边界扩展采样点数。"),
                    AccessorParameterSpec("figsize", "Matplotlib 图尺寸；None 使用视图默认布局。"),
                    AccessorParameterSpec("channel_filter", "仅 overlay 视图使用的通道筛选函数。"),
                    AccessorParameterSpec("show_sum", "仅 stacked 视图使用；是否显示求和波形。"),
                    AccessorParameterSpec(
                        "show_features", "仅 stacked 视图使用；要标注的特征名称列表。"
                    ),
                    AccessorParameterSpec(
                        "show_hit_windows", "仅 stacked 视图使用；是否显示 hit 窗口。"
                    ),
                    AccessorParameterSpec(
                        "show_merged_index", "仅 stacked 视图使用；是否标注代表 merged index。"
                    ),
                ),
                returns="`(figure, axes)`；overlay 视图也将单个轴包装为一元素 NumPy 数组。",
                notes=(
                    "需要安装 Matplotlib。",
                    "`sum-comparison` 用于对照两种波形构建路径，不应用作逐采样点相等性检验。",
                    "批量保存请在调用方显式循环 `plot()`、保存并关闭 figure。",
                ),
                example="""# 逐通道查看，并标注常用特征
fig, axes = accessor.plot(
    peak_id=919,
    view="stacked",
    show_features=["area", "height", "width"],
)

# 只叠加 board 0 的通道
fig, axes = accessor.plot(
    peak_id=919,
    view="overlay",
    channel_filter=lambda channel: channel["board"] == 0,
)

# 对照框架求和波形与各通道叠加
fig, axes = accessor.plot(peak_id=919, view="sum-comparison")
""",
            ),
        ),
    ),
    AccessorDocumentationSpec(
        accessor_class=S1S2PairAccessor,
        slug="s1-s2-pair-accessor",
        summary="查询 S1-S2 配对、关联 peak 的求和波形和位置重建结果，并支持可组合筛选与单配对绘图。",
        introduction=(
            "S1S2PairAccessor 把 S1-S2 配对表、筛选条件、求和波形和位置重建聚合为只读查询接口。"
            "配对表与波形层独立延迟加载，可先在 structured array 上构建条件，再读取少量候选的波形。"
        ),
        purpose=(
            '用于定位 S1/S2 关系、漂移时间、质量标志与重建位置。默认 `source="pairs"` 读取最终选择结果；'
            '需要检查全部候选时改用 `source="candidates"`；需要完整事件重建时改用 `source="events"`。'
        ),
        overview_title="整体介绍",
        overview_blocks=(
            DocumentationContentBlock(
                kind="paragraph",
                text=(
                    "`S1S2PairAccessor` 是只读查询接口：配对表负责提供 S1/S2 关系和事件级特征，"
                    "波形层按 peak ID 提供框架生成的求和波形，位置重建结果单独读取。"
                ),
            ),
            DocumentationContentBlock(
                kind="list",
                ordered=True,
                items=(
                    "先选择与分析目的一致的 `source`；",
                    "在 `pairs` structured array 上用 `mask()` 组合筛选条件；",
                    "仅对保留下来的少量 pair 查询波形、位置或调用 `plot()`。",
                ),
            ),
            DocumentationContentBlock(
                kind="note",
                title="数据访问范围",
                text=(
                    "所有读取都显式绑定构造器的 `run_id`。Accessor 不会重新执行配对、波形或位置重建插件；"
                    "它只查询 Context 中已有的产物。"
                ),
            ),
        ),
        narrative_sections=(
            AccessorNarrativeSection(
                anchor="pair-sources",
                title="配对数据源与查询范围",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "`source` 决定 `pairs` 属性读取的 structured array。三种来源均通过相同的 "
                            "`pair()`、`pairs_for_s1()`、`pairs_for_s2()` 和 `mask()` 接口访问。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="table",
                        table_headers=("source", "读取产物", "适用场景"),
                        table_rows=(
                            ("`pairs`", "`s1_s2_pairs`", "查看最终选择的 S1-S2 配对。"),
                            (
                                "`candidates`",
                                "`s1_s2_pair_candidates`",
                                "检查同一 S1 或 S2 的候选、排序与筛选结果。",
                            ),
                            (
                                "`events`",
                                "`events`",
                                "联合查看完整事件重建字段与 S1-S2 关系。",
                            ),
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "`selected_only=True` 仅在当前数据含有 `selected` 字段时生效；没有该字段时保留全部行。"
                            "它影响 `pairs`、按 S1/S2 查询和 `positions()` 的结果范围。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="note",
                        tone="important",
                        title="ID 与空结果",
                        text=(
                            "`pair(pair_id)` 找不到记录时返回 `None`；`pairs_for_s1()` 与 `pairs_for_s2()` "
                            "找不到记录时返回保留原 dtype 的空 structured array。"
                        ),
                    ),
                ),
            ),
            AccessorNarrativeSection(
                anchor="filtering-semantics",
                title="筛选掩码的组合语义",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "`mask()` 返回与 `pairs` 等长的布尔数组。所有已提供的条件以逻辑与组合，"
                            "因此可以直接使用 `accessor.pairs[mask]` 取得交集结果。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="table",
                        table_headers=("条件", "含义", "边界与缺失字段"),
                        table_rows=(
                            (
                                "范围条件",
                                "`drift_time_ns_range`、`log10_s2_s1_range`、`score_total_range`",
                                "范围端点包含在内；元组任一端为 `None` 表示不限制。`score_total` 缺失时忽略该条件。",
                            ),
                            (
                                "标志位条件",
                                "`flags_any`、`flags_all`、`flags_none`",
                                "分别对应任一命中、全部命中和完全不命中；`flags` 字段缺失时忽略。",
                            ),
                            (
                                "选择与自定义条件",
                                "`selected`、`custom_filter`",
                                "`selected` 在字段缺失时忽略；自定义函数接收完整 structured array，必须返回同长度布尔数组。",
                            ),
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="code",
                        language="python",
                        code="""mask = accessor.mask(\n    drift_time_ns_range=(10_000, 50_000),\n    flags_none=bad_quality_bits,\n    custom_filter=lambda pairs: pairs["s2_area"] > 5_000,\n)\nselected_pairs = accessor.pairs[mask]""",
                    ),
                ),
            ),
            AccessorNarrativeSection(
                anchor="waveforms-positions-cache",
                title="波形、位置与缓存",
                blocks=(
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "配对表与波形层独立延迟加载。访问 `pairs` 会加载当前 source 的表；首次调用 "
                            "`waveform()`、`pair_waveforms()` 或 `plot()` 才读取 `peaklet_waveforms` 和 "
                            "`peaklet_waveform_pool`。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="table",
                        table_headers=("接口", "返回或行为", "使用要点"),
                        table_rows=(
                            (
                                "`waveform(peak_id)`",
                                "单个 peak 的求和波形字典",
                                "默认返回缓存中的数组 view；需要原地修改时传入 `copy=True`。",
                            ),
                            (
                                "`pair_waveforms(pair_or_id)`",
                                "S1、S2 波形字典的二元组",
                                "可传入 pair ID 或 structured row；`missing='return_none'` 可避免缺失波形抛异常。",
                            ),
                            (
                                "`positions()`",
                                "位置重建 structured array",
                                "位置产物不存在时返回正确 dtype 的空数组；`selected_only=True` 时按当前 pair ID 过滤。",
                            ),
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="paragraph",
                        text=(
                            "`clear_cache()` 仅清除已提取的 waveform view；`release_layer()` 还会释放原始波形层。"
                            "释放后下一次波形请求会重新从 Context 读取数据。"
                        ),
                    ),
                    DocumentationContentBlock(
                        kind="note",
                        title="绘图时间轴",
                        text=(
                            "`plot()` 以 S1 波形起点为零点，将 S1 与 S2 放到同一相对时间轴。`pad_ns` 控制显示窗口两端的额外范围，"
                            "`show_info=True` 会在标题中加入可用的漂移时间、面积、评分、排序和选择状态。"
                        ),
                    ),
                ),
            ),
        ),
        example="""from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor

accessor = S1S2PairAccessor(ctx, run_id="run_001", selected_only=True)
mask = accessor.mask(
    drift_time_ns_range=(10_000, 50_000),
    log10_s2_s1_range=(1.5, None),
)
filtered = accessor.pairs[mask]""",
        constructor_parameters=(
            AccessorParameterSpec("context", "已配置插件和数据存储的 Context。"),
            AccessorParameterSpec("run_id", "本次查询对应的 run ID。"),
            AccessorParameterSpec(
                "source",
                '`"pairs"` 读取最终配对；`"candidates"` 读取所有候选配对；`"events"` 读取完整事件重建结果。',
            ),
            AccessorParameterSpec(
                "selected_only", "为 `True` 时仅保留 `selected=True` 的行（字段存在时）。"
            ),
            AccessorParameterSpec("lazy_pairs", "为 `True` 时延迟加载配对表。"),
            AccessorParameterSpec(
                "lazy_waveform", "为 `True` 时延迟加载 peaklet 波形层，推荐保留默认值。"
            ),
        ),
        members=(
            AccessorMemberSpec(
                "pairs",
                "访问当前范围内的全部配对 structured array。",
                "property",
                returns="`np.ndarray` structured array。首次访问会加载配对表。",
            ),
            AccessorMemberSpec(
                "pair",
                "按 pair ID 返回一个完整 structured row。",
                parameters=(AccessorParameterSpec("pair_id", "目标配对的整数 ID。"),),
                returns="匹配的 `np.void` row；找不到时返回 `None`。",
            ),
            AccessorMemberSpec(
                "pairs_for_s1",
                "返回指定 S1 关联的全部配对。",
                parameters=(AccessorParameterSpec("s1_peak_id", "S1 peak 的整数 ID。"),),
                returns="保留原 dtype 的 structured array；无匹配时为空数组。",
            ),
            AccessorMemberSpec(
                "pairs_for_s2",
                "返回指定 S2 关联的全部配对。",
                parameters=(AccessorParameterSpec("s2_peak_id", "S2 peak 的整数 ID。"),),
                returns="保留原 dtype 的 structured array；无匹配时为空数组。",
            ),
            AccessorMemberSpec(
                "mask",
                "根据物理量范围、标志位和自定义函数构建布尔筛选掩码。",
                parameters=(
                    AccessorParameterSpec(
                        "drift_time_ns_range",
                        "漂移时间 `(min_ns, max_ns)`；边界可用 `None` 表示不限制。",
                    ),
                    AccessorParameterSpec(
                        "log10_s2_s1_range", "`log10(S2/S1)` 的 `(min, max)` 范围。"
                    ),
                    AccessorParameterSpec(
                        "score_total_range", "总分的 `(min, max)` 范围；字段不存在时忽略。"
                    ),
                    AccessorParameterSpec("flags_any", "要求至少命中一个给定位掩码。"),
                    AccessorParameterSpec("flags_all", "要求命中全部给定位掩码。"),
                    AccessorParameterSpec("flags_none", "要求不命中任一给定位掩码。"),
                    AccessorParameterSpec("selected", "按 `selected` 字段筛选；字段不存在时忽略。"),
                    AccessorParameterSpec(
                        "custom_filter", "接收完整 structured array 并返回布尔数组的函数。"
                    ),
                ),
                returns="与 `pairs` 等长的 `np.ndarray[bool]`，`True` 表示保留。",
                example="""mask = accessor.mask(
    drift_time_ns_range=(10_000, 50_000),
    score_total_range=(0.8, None),
    selected=True,
)
candidate_pairs = accessor.pairs[mask]
""",
            ),
            AccessorMemberSpec(
                "waveform",
                "按 peak ID 读取求和波形。",
                parameters=(
                    AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),
                    AccessorParameterSpec(
                        "copy", "为 `True` 时复制 waveform 数组，避免修改缓存 view。"
                    ),
                ),
                returns="含 `waveform`、`time_start_ns`、`time_rel_ns`、`dt_ns` 的字典；缺失时为 `None`。",
            ),
            AccessorMemberSpec(
                "pair_waveforms",
                "同时取得一个配对的 S1 和 S2 求和波形。",
                parameters=(
                    AccessorParameterSpec("pair_or_id", "pair ID 或一条 structured pair row。"),
                    AccessorParameterSpec("copy", "是否复制 waveform 数组。"),
                    AccessorParameterSpec(
                        "missing", '`"raise"` 在缺失时抛异常；`"return_none"` 返回 `None`。'
                    ),
                ),
                returns="`(s1_waveform, s2_waveform)`；按 `missing` 策略处理缺失。",
            ),
            AccessorMemberSpec("clear_cache", "清空已提取的 waveform 缓存。", returns="无返回值。"),
            AccessorMemberSpec(
                "release_layer",
                "释放原始波形层和缓存，下一次波形查询会重新加载。",
                returns="无返回值。",
            ),
            AccessorMemberSpec(
                "plot",
                "以 S1 起点为零点，在统一时间轴上绘制 S1 和 S2 波形。",
                parameters=(
                    AccessorParameterSpec("pair_or_id", "pair ID 或一条 structured pair row。"),
                    AccessorParameterSpec("pad_ns", "波形两端增加的时间范围，单位 ns。"),
                    AccessorParameterSpec(
                        "show_info", "是否在标题显示漂移时间、面积、评分等信息。"
                    ),
                    AccessorParameterSpec("ax", "目标 Matplotlib axes；`None` 时创建新 figure。"),
                ),
                returns="`(figure, axes)`。",
                notes=("需要安装 Matplotlib；缺失波形会抛出异常。",),
            ),
            AccessorMemberSpec(
                "positions",
                "返回与当前配对范围对应的位置重建数据。",
                returns="`np.ndarray` structured array；位置数据不存在时返回正确 dtype 的空数组。",
                notes=("`selected_only=True` 时结果也会按当前配对集合过滤。",),
            ),
        ),
    ),
)


_PARAMETER_HELP = {
    "storage_backend": "可选存储后端实例。",
    "storage_dir": "本地缓存目录。",
    "config": "Context 的显式配置字典。",
    "external_plugin_dirs": "额外插件发现目录。",
    "auto_discover_plugins": "是否在构造时自动发现插件。",
    "stats_mode": "统计记录模式。",
    "stats_log_file": "可选统计日志文件路径。",
    "plugins": "要注册的插件实例、类、模块或其序列。",
    "allow_override": "同名 `provides` 已注册时是否允许覆盖。",
    "require_spec": "是否要求插件具备完整声明规范。",
    "run_id": "显式指定要访问、执行或诊断的运行 ID。",
    "data_name": "已注册插件提供的数据名称。",
    "plugin": "插件实例或其 `provides` 名称。",
    "plugin_name": "插件的 `provides` 名称。",
    "name": "配置项名称。",
    "adapter_name": "覆盖自动推断的 DAQ adapter 名称。",
    "refresh": "是否忽略已有 run 配置并重新读取。",
    "target": "要解析依赖的数据名称。",
    "target_name": "要分析依赖的数据名称。",
    "kind": "lineage 输出类型：`labview`、`plotly` 或 `mermaid`。",
    "show_virtual_plugins": "是否显示仅用于可视化的虚拟插件节点。",
    "include_performance": "是否将性能信息纳入依赖分析。",
    "topic": "帮助主题；省略时返回 Context 总览。",
    "output": "返回形态：`native`、`chunk_stream` 或 `array`。",
    "show_progress": "是否显示数据请求进度。",
    "progress_desc": "可选进度显示文本。",
    "kwargs": "传递给目标插件的数据请求参数。",
    "time_field": "开始时间字段名；省略时自动推断。",
    "endtime_field": "结束时间字段名；省略时自动推断。",
    "force_rebuild": "是否强制重建已有时间索引。",
    "time_domain": "查询时间域，默认 `system_ns`。",
    "start_time": "系统时间范围的起点。",
    "end_time": "系统时间范围的终点。",
    "auto_build_index": "索引缺失时是否自动建立。",
    "epoch": "要设置的绝对时间基准。",
    "time_unit": "数值 epoch 的单位。",
    "start_dt": "绝对时间范围的起点。",
    "end_dt": "绝对时间范围的终点。",
    "auto_extract_epoch": "epoch 缺失时是否自动从数据提取。",
    "show_tree": "是否显示依赖树。",
    "show_config": "是否显示解析后的配置。",
    "show_usage": "是否显示每项配置的使用位置。",
    "show_full_help": "是否显示完整帮助文本。",
    "run_name": "仅用于展示的运行名称。",
    "show_cache": "是否显示缓存命中状态。",
    "verbose": "输出详细程度。",
    "_visited": "内部循环检测状态；调用方无需传递。",
    "downstream": "是否同时清理下游产物。",
    "clear_memory": "是否清理内存缓存。",
    "clear_disk": "是否清理磁盘缓存。",
    "auto_fix": "是否执行可自动修复的诊断建议。",
    "dry_run": "仅报告诊断结果而不修改缓存。",
    "detailed": "是否返回详细统计。",
    "export_path": "可选统计导出路径。",
    "data": "长度一致的一维变量数组序列。",
    "names": "变量名称列表。",
    "bins": "直方图分箱数或每个变量的分箱边界。",
    "ranges": "每个变量的显示范围。",
    "scales": "线性或对数坐标设置。",
    "weights": "与样本等长的可选权重。",
    "figsize_per_panel": "每个矩阵面板的边长。",
    "cmap": "二维直方图色图。",
    "hist_color": "对角线直方图颜色。",
    "hist2d_norm": "二维直方图归一化方式。",
    "hist2d_vmin": "二维直方图色标下限。",
    "hist2d_vmax": "二维直方图色标上限。",
    "add_colorbar": "是否添加二维直方图色条。",
    "title": "图标题。",
    "min_count": "显示二维 bin 的最小计数。",
    "hist_alpha": "一维直方图透明度。",
    "hist2d_alpha": "二维直方图透明度。",
    "fig": "可选复用的 Matplotlib figure。",
    "axes": "corner 矩阵的 Matplotlib axes。",
    "triangle": "显示 `lower`、`upper` 或 `full` 矩阵区域。",
    "label_mode": "轴标签显示方式。",
    "label_fontsize": "轴标签字号。",
    "label_fontweight": "轴标签字重。",
    "tick_labelsize": "刻度字号。",
    "diag_title": "是否在对角线显示变量标题。",
    "show_ticks": "是否显示刻度。",
    "var": "要添加一维阈值的变量名。",
    "value": "一维阈值位置。",
    "xvar": "二维曲线的 x 变量名。",
    "yvar": "二维曲线的 y 变量名。",
    "y_func": "接收 x 数组并返回 y 边界的函数。",
    "x_range": "二维曲线采样的 x 范围。",
    "n_points": "曲线采样点数。",
    "color": "叠加线颜色。",
    "linestyle": "叠加线型。",
    "linewidth": "叠加线宽。",
    "label": "图例标签。",
    "waveforms": "波形数组列表、二维数组或带 board/channel 的 structured array。",
    "channel": '可选通道筛选，推荐 `(board, channel)` 或 `"board:channel"`。',
    "hits": "可选 hit structured array，用于标注。",
    "event_index": "要显示的事件索引。",
    "channels": '待显示通道；使用 `(board, channel)`、`"board:channel"` 或 `HardwareChannel`。',
    "context": "已配置插件和存储的 Context。",
    "peak_id": "目标 peak 的整数 ID。",
    "pad": "hit 窗口两端扩展的采样点数。",
    "group_by": "按 `channel` 或 `board_channel` 分组。",
}

_CALLABLE_RETURNS = {
    "Context": "已配置但未绑定当前 run 的 `Context` 实例。",
    "list_provided_data": "已注册插件的 `provides` 名称列表。",
    "get_plugin": "匹配的 `Plugin` 实例。",
    "get_config_value": "带来源信息的 `ConfigValue`。",
    "get_resolved_config": "插件的 `ResolvedConfig`。",
    "get_run_config": "指定 run 的配置字典。",
    "get_data": "请求的原生结果、数组或 chunk stream。",
    "build_time_index": "时间索引元数据字典。",
    "time_range": "命中时间范围的数组或数组列表。",
    "get_epoch": "指定 run 的 epoch；未设置时为 `None`。",
    "get_data_time_range_absolute": "命中绝对时间范围的数组或数组列表。",
    "resolve_dependencies": "按执行顺序排列的依赖名称列表。",
    "preview_execution": "执行计划、配置与缓存状态字典。",
    "get_lineage": "目标产物的 lineage 字典。",
    "plot_lineage": "图形对象或 Mermaid 文本，取决于 `kind`。",
    "analyze_dependencies": "依赖分析结果。",
    "help": "结构化 `HelpDocument`。",
    "clear_cache_for": "已清理的缓存条目数。",
    "analyze_cache": "`CacheAnalyzer` 分析器。",
    "diagnose_cache": "诊断问题列表。",
    "cache_stats": "`CacheStatistics` 汇总结果。",
    "corner_hist": "`(matplotlib.figure.Figure, numpy.ndarray)`。",
    "plot_waveforms": "交互式 Plotly figure；Plotly 缺失时返回 `None`。",
    "plot_peak_channels_with_sum": "`(figure, axes)`；没有 peak 数据时均为 `None`。",
    "create_peak_plotter": "预加载数据的 `plot_func(peak_id, pad, group_by)`。",
}

_CALLABLE_NOTES = {
    "Context": ("Context 无状态；数据访问必须显式传入 `run_id`。",),
    "register": ("插件行为变更后应升级插件版本，以保证缓存 lineage 失效。",),
    "get_data": ("请求会按需解析依赖并复用有效缓存。",),
    "preview_execution": ("只分析元数据，不执行插件或加载 run 数据。",),
    "plot_lineage": ("`mermaid` 返回文本；`labview` 和 `plotly` 返回图形对象。",),
    "clear_cache_for": ("设置 `downstream=True` 前应确认影响范围。",),
    "diagnose_cache": ("默认 `dry_run=True`，不会修改缓存。",),
    "corner_hist": ("对数坐标要求对应数据和范围为正数。",),
    "plot_peak_channels_with_sum": ("批量检查多个 peak 时应使用 `create_peak_plotter()`。",),
    "create_peak_plotter": ("返回函数会持有预加载数组，使用完毕后释放引用。",),
}

_CALLABLE_EXAMPLES = {
    "Context": """ctx = Context(config={\"data_root\": \"DAQ\", \"daq_adapter\": \"vx2730\"})\nctx.register(*profiles.cpu_default())""",
    "get_data": """peaks = ctx.get_data(\"run_001\", \"peaks\")""",
    "preview_execution": """plan = ctx.preview_execution(\"run_001\", \"peaks\")""",
    "plot_lineage": """figure = ctx.plot_lineage(\"peaks\", kind=\"plotly\", show_virtual_plugins=False)""",
    "clear_cache_for": """ctx.clear_cache_for(\"run_001\", \"peaks\", downstream=True)""",
    "plot_waveforms": """figure = plot_waveforms(waveforms, event_index=0, channels=[\"0:3\"])""",
    "plot_peak_channels_with_sum": """fig, axes = plot_peak_channels_with_sum(919, context=ctx, run_id=\"run_001\")""",
    "create_peak_plotter": """plot_peak = create_peak_plotter(ctx, \"run_001\")\nfig, axes = plot_peak(919)""",
}


def _callable_parameters(callable_obj: Any) -> tuple[AccessorParameterSpec, ...]:
    return tuple(
        AccessorParameterSpec(name, _PARAMETER_HELP.get(name, f"`{name}` 的调用参数。"))
        for name in inspect.signature(callable_obj).parameters
        if name != "self"
    )


def _context_spec(name: str, description: str) -> CallableDocumentationSpec:
    target = Context if name == "Context" else getattr(Context, name)
    return CallableDocumentationSpec(
        name,
        target,
        description,
        _callable_parameters(target),
        returns=_CALLABLE_RETURNS.get(name, "无返回值；结果通过 Context 状态或终端输出呈现。"),
        notes=_CALLABLE_NOTES.get(name, ()),
        example=_CALLABLE_EXAMPLES.get(name, ""),
        kind="class" if name == "Context" else "function",
    )


CONTEXT_DOCUMENTATION_PAGE = CallableDocumentationPageSpec(
    "context",
    "Context",
    "分析运行时",
    "管理显式 run_id、配置、插件 DAG、数据访问与缓存诊断的分析入口。",
    "`Context` 不保存隐式当前运行。每次数据访问都传入 `run_id`，由它解析插件依赖、准备配置并复用 lineage 一致的缓存。",
    (
        CallableDocumentationGroup(
            "initialization",
            "初始化与插件注册",
            "创建 Context，注册或发现插件，并检查已提供的数据产物。",
            tuple(
                _context_spec(*item)
                for item in (
                    ("Context", "创建分析 Context；构造器不绑定某个 run。"),
                    ("register", "注册插件实例、插件类、模块或其序列。"),
                    ("discover_and_register_plugins", "从 entry point 与配置目录发现插件。"),
                    ("list_provided_data", "列出已注册的稳定数据名称。"),
                    ("get_plugin", "按 `provides` 名称取得插件实例。"),
                )
            ),
        ),
        CallableDocumentationGroup(
            "configuration",
            "配置解析",
            "显式配置优先于 adapter 推断和插件默认值。",
            tuple(
                _context_spec(*item)
                for item in (
                    ("set_config", "设置全局或插件显式配置。"),
                    ("get_config_value", "读取单项配置及其解析来源。"),
                    ("get_resolved_config", "返回插件完整解析配置。"),
                    ("show_resolved_config", "打印解析配置。"),
                    ("show_config", "显示当前配置，并标识每个配置项对应的插件。"),
                    ("get_run_config", "读取特定 run 的 DAQ 配置。"),
                )
            ),
        ),
        CallableDocumentationGroup(
            "data-access",
            "数据访问与时间查询",
            "按需请求插件产物，并在系统或绝对时间域中切片。",
            tuple(
                _context_spec(*item)
                for item in (
                    ("get_data", "请求 run 的具名数据；未命中缓存时执行必要上游。"),
                    ("build_time_index", "建立或刷新时间索引。"),
                    ("time_range", "在系统时间 ns 域查询范围。"),
                    ("set_epoch", "设置 run 的绝对时间 epoch。"),
                    ("get_epoch", "读取 run 的 epoch。"),
                    ("get_data_time_range_absolute", "使用 datetime 边界查询绝对时间范围。"),
                )
            ),
        ),
        CallableDocumentationGroup(
            "dag-and-execution",
            "依赖、执行与 DAG",
            "在执行前查看计划与依赖；`plot_lineage()` 是 Context 的 DAG 调试能力。",
            tuple(
                _context_spec(*item)
                for item in (
                    ("resolve_dependencies", "返回目标依赖执行顺序。"),
                    ("preview_execution", "预览执行计划、配置与缓存命中。"),
                    ("get_lineage", "返回插件 lineage 数据结构。"),
                    ("plot_lineage", "渲染 `labview`、`plotly` 或 `mermaid` DAG。"),
                    ("analyze_dependencies", "分析上游、下游与性能信息。"),
                    ("help", "返回结构化帮助文档。"),
                )
            ),
        ),
        CallableDocumentationGroup(
            "cache-diagnostics",
            "缓存与诊断",
            "缓存 key 由 run、代码、版本、配置和输出契约决定。",
            tuple(
                _context_spec(*item)
                for item in (
                    ("clear_cache_for", "清理指定 run 的缓存。"),
                    ("analyze_cache", "生成缓存状态分析。"),
                    ("diagnose_cache", "诊断缓存问题，默认 dry-run。"),
                    ("cache_stats", "汇总缓存统计。"),
                )
            ),
        ),
    ),
)


VISUALIZATION_DOCUMENTATION_PAGES = (
    CallableDocumentationPageSpec(
        "statistical-plots",
        "统计图",
        "可视化",
        "使用 corner plot 探索多变量分布，并叠加一维或二维选择条件。",
        "先由 `corner_hist()` 创建矩阵，再将筛选线或曲线叠加到同一组 axes。",
        (
            CallableDocumentationGroup(
                "statistical-plots",
                "统计图函数",
                "基于 Matplotlib 的分布与选择条件检查。",
                (
                    CallableDocumentationSpec(
                        "corner_hist",
                        corner_hist,
                        "创建含一维与二维直方图的 corner 矩阵。",
                        _callable_parameters(corner_hist),
                        returns=_CALLABLE_RETURNS["corner_hist"],
                        notes=_CALLABLE_NOTES["corner_hist"],
                        example="""fig, axes = corner_hist([area, height, width], names=[\"area\", \"height\", \"width\"])
plot_1d_cut_on_corner(axes, [\"area\", \"height\", \"width\"], \"area\", 1000)
plot_2d_cut_on_corner(axes, [\"area\", \"height\", \"width\"], \"area\", \"height\", lambda x: 0.1 * x)
fig.savefig(\"corner.png\", dpi=150)
""",
                    ),
                    CallableDocumentationSpec(
                        "plot_1d_cut_on_corner",
                        plot_1d_cut_on_corner,
                        "叠加一维阈值线。",
                        _callable_parameters(plot_1d_cut_on_corner),
                        returns="无返回值；在传入 axes 上添加阈值线。",
                        notes=("`triangle` 必须与 `corner_hist()` 的设置一致。",),
                    ),
                    CallableDocumentationSpec(
                        "plot_2d_cut_on_corner",
                        plot_2d_cut_on_corner,
                        "叠加二维选择曲线。",
                        _callable_parameters(plot_2d_cut_on_corner),
                        returns="无返回值；在传入 axes 上添加选择曲线。",
                        notes=("`y_func` 必须接受 NumPy 数组输入。",),
                    ),
                ),
            ),
        ),
    ),
    CallableDocumentationPageSpec(
        "waveform-plots",
        "波形图",
        "可视化",
        "使用 Plotly 浏览多通道波形，或检查 peak 通道波形与求和波形。",
        "Context 驱动的波形访问均显式指定 `run_id`。",
        (
            CallableDocumentationGroup(
                "waveform-plots",
                "波形图函数",
                "Plotly 适合交互浏览；批量 peak 检查应复用 plotter。",
                (
                    CallableDocumentationSpec(
                        "plot_waveforms",
                        plot_waveforms,
                        "创建原始波形与可选 hit 标注的交互图。",
                        _callable_parameters(plot_waveforms),
                        returns=_CALLABLE_RETURNS["plot_waveforms"],
                        example=_CALLABLE_EXAMPLES["plot_waveforms"],
                    ),
                    CallableDocumentationSpec(
                        "plot_peak_channels_with_sum",
                        plot_peak_channels_with_sum,
                        "绘制单个 peak 的逐通道与求和波形。",
                        _callable_parameters(plot_peak_channels_with_sum),
                        returns=_CALLABLE_RETURNS["plot_peak_channels_with_sum"],
                        notes=_CALLABLE_NOTES["plot_peak_channels_with_sum"],
                        example=_CALLABLE_EXAMPLES["plot_peak_channels_with_sum"],
                    ),
                    CallableDocumentationSpec(
                        "create_peak_plotter",
                        create_peak_plotter,
                        "创建绑定 Context 和 run_id 的可复用 peak 绘图函数。",
                        _callable_parameters(create_peak_plotter),
                        returns=_CALLABLE_RETURNS["create_peak_plotter"],
                        notes=_CALLABLE_NOTES["create_peak_plotter"],
                        example=_CALLABLE_EXAMPLES["create_peak_plotter"],
                    ),
                ),
            ),
        ),
    ),
)


def _highlight_python(source: str) -> Markup:
    """Return trusted offline Pygments markup for registry-controlled Python examples."""
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import PythonLexer
    except ImportError as exc:
        raise RuntimeError(
            "site-web Accessor examples require Pygments. Install the documentation extra: "
            'pip install -e ".[docgen]"'
        ) from exc
    return Markup(highlight(source, PythonLexer(), HtmlFormatter(nowrap=True)))


def _inline_code(value: str) -> Markup:
    """Escape prose first, then render restricted emphasis and code notation."""
    escaped = str(escape(value))
    emphasized = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return Markup(re.sub(r"`([^`]+)`", r"<code>\1</code>", emphasized))


class DocumentationSiteGenerator:
    """Compose plugin and curated Accessor documentation into one offline site."""

    def __init__(
        self,
        plugin_generator: PluginDocGenerator | None = None,
        accessor_registry: tuple[AccessorDocumentationSpec, ...] = ACCESSOR_DOCUMENTATION_REGISTRY,
    ):
        self.plugin_generator = plugin_generator or PluginDocGenerator()
        self.accessor_registry = accessor_registry

    def build_accessor_views(self) -> list[AccessorDocumentationView]:
        views = []
        slugs: set[str] = set()
        for spec in self.accessor_registry:
            if spec.slug in slugs:
                raise ValueError(f"Duplicate Accessor documentation slug: {spec.slug}")
            slugs.add(spec.slug)
            members = []
            for member_spec in spec.members:
                try:
                    raw_member = inspect.getattr_static(spec.accessor_class, member_spec.name)
                except AttributeError as exc:
                    raise ValueError(
                        f"Registered member {spec.accessor_class.__name__}.{member_spec.name} does not exist"
                    ) from exc
                is_property = isinstance(raw_member, property)
                expected_property = member_spec.kind == "property"
                if is_property != expected_property:
                    raise ValueError(
                        f"Registered member kind mismatch for {spec.accessor_class.__name__}.{member_spec.name}"
                    )
                target: Any = raw_member.fget if is_property else raw_member
                if target is None or not callable(target):
                    raise ValueError(
                        f"Registered member {spec.accessor_class.__name__}.{member_spec.name} is not callable"
                    )
                signature = inspect.signature(target)
                rendered_signature = self._format_signature(signature)
                members.append(
                    AccessorMemberView(
                        name=member_spec.name,
                        kind=member_spec.kind,
                        signature=rendered_signature,
                        signature_html=_highlight_python(
                            f"def {member_spec.name}{rendered_signature}:"
                        ),
                        description=member_spec.description,
                        parameters=self._validated_parameters(
                            signature,
                            member_spec.parameters,
                            f"{spec.accessor_class.__name__}.{member_spec.name}",
                        ),
                        returns=member_spec.returns,
                        notes=member_spec.notes,
                        example_html=(
                            _highlight_python(member_spec.example)
                            if member_spec.example
                            else Markup("")
                        ),
                    )
                )
            constructor_signature = inspect.signature(spec.accessor_class)
            views.append(
                AccessorDocumentationView(
                    name=spec.accessor_class.__name__,
                    slug=spec.slug,
                    module_path=spec.accessor_class.__module__,
                    summary=spec.summary,
                    introduction=spec.introduction,
                    purpose=spec.purpose,
                    example_html=_highlight_python(spec.example),
                    constructor_signature=str(constructor_signature),
                    constructor_parameters=self._validated_parameters(
                        constructor_signature,
                        spec.constructor_parameters,
                        spec.accessor_class.__name__,
                    ),
                    members=tuple(members),
                    narrative_sections=spec.narrative_sections,
                    overview_title=spec.overview_title,
                    overview_blocks=spec.overview_blocks,
                )
            )
        return views

    def build_callable_page_view(
        self, spec: CallableDocumentationPageSpec
    ) -> CallableDocumentationPageView:
        groups = []
        for group in spec.groups:
            members = tuple(
                CallableDocumentationView(
                    name=item.name,
                    signature_html=_highlight_python(
                        f"{'class' if item.kind == 'class' else 'def'} {item.name}"
                        f"{self._format_signature(inspect.signature(item.callable))}:"
                    ),
                    description=item.description,
                    parameters=self._validated_parameters(
                        inspect.signature(item.callable), item.parameters, item.name
                    ),
                    returns=item.returns,
                    notes=item.notes,
                    example_html=_highlight_python(item.example) if item.example else Markup(""),
                    kind=item.kind,
                )
                for item in group.members
            )
            groups.append((group, members))
        return CallableDocumentationPageView(
            spec.slug, spec.title, spec.eyebrow, spec.summary, spec.introduction, tuple(groups)
        )

    @staticmethod
    def _format_signature(signature: inspect.Signature, max_width: int = 96) -> str:
        """Render long callable signatures one parameter per line for the HTML reference."""
        rendered = str(signature)
        if len(rendered) <= max_width:
            return rendered

        parameters = ",\n".join(f"    {parameter}" for parameter in signature.parameters.values())
        return_annotation = ""
        if signature.return_annotation is not inspect.Signature.empty:
            annotation = signature.return_annotation
            if annotation is np.ndarray:
                annotation = "np.ndarray"
            return_annotation = f" -> {annotation}"
        return f"(\n{parameters},\n){return_annotation}"

    @staticmethod
    def _validated_parameters(
        signature: inspect.Signature,
        documented: tuple[AccessorParameterSpec, ...],
        subject: str,
    ) -> tuple[AccessorParameterSpec, ...]:
        """Keep prose descriptions synchronized with the live callable signature."""
        live_names = tuple(name for name in signature.parameters if name != "self")
        documented_names = tuple(parameter.name for parameter in documented)
        if live_names != documented_names:
            raise ValueError(
                f"Registered parameter names for {subject} do not match signature: "
                f"expected {live_names}, got {documented_names}"
            )
        return documented

    def _copy_content_assets(
        self,
        views: list[AccessorDocumentationView],
        asset_dir: Path,
        generated: dict[str, Path],
    ) -> None:
        """Copy only registry-referenced documentation images into the offline site."""
        source_dir = self.plugin_generator.template_dir / "web" / "content-assets"
        image_sources = {
            block.image_src
            for view in views
            for section in view.narrative_sections
            for block in section.blocks
            if block.kind == "image"
        }
        for image_src in sorted(image_sources):
            relative_path = Path(PurePosixPath(image_src))
            source_path = source_dir / relative_path
            if not source_path.is_file():
                raise ValueError(
                    f"Documentation image {image_src!r} is not present in {source_dir}"
                )
            target_path = asset_dir / "content" / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            generated[f"asset:content/{image_src}"] = target_path

    def generate(self, output_dir: Path) -> dict[str, Path]:
        output_dir = Path(output_dir)
        self.plugin_generator.load_builtin_plugins()
        views = self.build_accessor_views()
        context_view = self.build_callable_page_view(CONTEXT_DOCUMENTATION_PAGE)
        visualization_views = [
            self.build_callable_page_view(spec) for spec in VISUALIZATION_DOCUMENTATION_PAGES
        ]
        site_search_entries = [
            {
                "title": "Context 与 Plugin 入门",
                "summary": "Context 管理 run_id、配置、插件依赖和缓存；Plugin 负责产出具名数据。",
                "kind": "入门",
                "url": "index.html#context-and-plugin",
                "keywords": "Context Plugin 插件 DAG run_id 配置 缓存 依赖",
            },
            {
                "title": "Context 最小流程",
                "summary": "创建 Context、注册 cpu_default 插件集，再通过 get_data 请求目标产物。",
                "kind": "入门",
                "url": "index.html#minimal-workflow",
                "keywords": "Context register cpu_default get_data peaks run_id 最小示例",
            },
        ]
        for view in views:
            base_url = f"accessors/{view.slug}.html"
            site_search_entries.extend(
                {
                    "title": view.name,
                    "summary": view.summary,
                    "kind": "Accessor",
                    "url": f"{base_url}{anchor}",
                    "keywords": f"{view.name} {view.summary} {heading}",
                }
                for heading, anchor in (
                    ("整体介绍", "#overview"),
                    ("构造器", "#constructor"),
                    ("快速开始", "#quickstart"),
                    ("公开成员", "#members"),
                )
            )
        for view in (context_view, *visualization_views):
            section = "contexts" if view.slug == "context" else "visualizations"
            for group, members in view.groups:
                site_search_entries.append(
                    {
                        "title": f"{view.title}: {group.title}",
                        "summary": group.description,
                        "kind": "Context" if section == "contexts" else "可视化",
                        "url": f"{section}/{view.slug}.html#{group.anchor}",
                        "keywords": f"{view.title} {group.title} "
                        + " ".join(member.name for member in members),
                    }
                )
        env = self.plugin_generator._get_web_jinja_env()
        env.filters["inline_code"] = _inline_code
        env.filters["mathml"] = _safe_mathml
        generated = self.plugin_generator.generate_web(
            output_dir,
            index_relative_path="plugins/index.html",
            plugin_relative_dir="plugins",
            asset_relative_dir="assets",
            site_home_href="index.html",
            accessor_relative_path="accessors/index.html",
            context_relative_path="contexts/index.html",
            visualization_relative_path="visualizations/index.html",
            extra_search_entries=site_search_entries,
        )
        self._copy_content_assets(views, output_dir / "assets", generated)
        accessor_dir = output_dir / "accessors"
        accessor_dir.mkdir(parents=True, exist_ok=True)
        home_path = output_dir / "index.html"
        context_plugin_example = """from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

run_id = \"run_001\"
ctx = Context(config={\"data_root\": \"DAQ\", \"daq_adapter\": \"vx2730\"})
ctx.register(*profiles.cpu_default())

# Context resolves the plugin DAG and reuses available cache entries.
peaks = ctx.get_data(run_id, \"peaks\")"""
        home_path.write_text(
            env.get_template("web/site_index.html.j2").render(
                accessor_count=len(views),
                context_view=context_view,
                visualization_views=visualization_views,
                context_plugin_example_html=_highlight_python(context_plugin_example),
            ),
            encoding="utf-8",
        )
        generated["SITE_INDEX"] = home_path
        accessor_index = accessor_dir / "index.html"
        accessor_index.write_text(
            env.get_template("web/accessor_index.html.j2").render(accessors=views),
            encoding="utf-8",
        )
        generated["ACCESSOR_INDEX"] = accessor_index
        for view in views:
            path = accessor_dir / f"{view.slug}.html"
            path.write_text(
                env.get_template("web/accessor.html.j2").render(accessor=view),
                encoding="utf-8",
            )
            generated[f"accessor:{view.slug}"] = path
        context_dir = output_dir / "contexts"
        context_dir.mkdir(parents=True, exist_ok=True)
        context_index = context_dir / "index.html"
        context_index.write_text(
            env.get_template("web/callable_index.html.j2").render(
                title="Context",
                eyebrow="分析运行时",
                summary=context_view.summary,
                pages=(context_view,),
                current_section="contexts",
            ),
            encoding="utf-8",
        )
        generated["CONTEXT_INDEX"] = context_index
        context_path = context_dir / "context.html"
        context_path.write_text(
            env.get_template("web/callable_reference.html.j2").render(
                page=context_view, current_section="contexts", index_title="Context"
            ),
            encoding="utf-8",
        )
        generated["context:context"] = context_path
        visualization_dir = output_dir / "visualizations"
        visualization_dir.mkdir(parents=True, exist_ok=True)
        visualization_index = visualization_dir / "index.html"
        visualization_index.write_text(
            env.get_template("web/callable_index.html.j2").render(
                title="可视化",
                eyebrow="参考",
                summary="统计图与波形图的公开绘图接口。",
                pages=visualization_views,
                current_section="visualizations",
            ),
            encoding="utf-8",
        )
        generated["VISUALIZATION_INDEX"] = visualization_index
        for view in visualization_views:
            path = visualization_dir / f"{view.slug}.html"
            path.write_text(
                env.get_template("web/callable_reference.html.j2").render(
                    page=view, current_section="visualizations", index_title="可视化"
                ),
                encoding="utf-8",
            )
            generated[f"visualization:{view.slug}"] = path
        return generated
