"""Internal generator for the offline WaveformAnalysis documentation site."""

from dataclasses import dataclass
import inspect
from pathlib import Path
import re
from typing import Any

from markupsafe import Markup, escape

from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor
from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator
from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor


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
class AccessorDocumentationSpec:
    accessor_class: type
    slug: str
    summary: str
    introduction: str
    purpose: str
    example: str
    constructor_parameters: tuple[AccessorParameterSpec, ...]
    members: tuple[AccessorMemberSpec, ...]


@dataclass(frozen=True)
class AccessorMemberView:
    name: str
    kind: str
    signature: str
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


ACCESSOR_DOCUMENTATION_REGISTRY = (
    AccessorDocumentationSpec(
        accessor_class=PeakChannelAccessor,
        slug="peak-channel-accessor",
        summary="按 peak 查询各硬件通道的特征与波形，并提供常用对比绘图。",
        introduction=(
            "PeakChannelAccessor 面向单个 peak 的通道级排查。它先读取轻量的特征层，"
            "只有请求波形或绘图时才读取 records 与 wave pool，因此适合先用面积和高度筛选，"
            "再针对少量候选做波形检查。"
        ),
        purpose=(
            "返回通道唯一键 `(board, channel)` 下的聚合特征；当 `peaklet_channels` 可用时，"
            "其中的 `area`、`height`、`n_hits` 与 `area_fraction` 是每通道聚合值。"
        ),
        example="""from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(ctx, run_id="run_001", lazy_load=True)
channels = accessor.get_peak_channels(peak_id=919)""",
        constructor_parameters=(
            AccessorParameterSpec("context", "已配置插件和数据存储的 Context。"),
            AccessorParameterSpec("run_id", "本次查询对应的 run ID，所有访问都显式绑定到该 run。"),
            AccessorParameterSpec(
                "lazy_load", "为 `True` 时延迟读取特征层；适合先创建多个访问器但不立即查询的场景。"
            ),
        ),
        members=(
            AccessorMemberSpec(
                "get_peak_channels",
                "返回一个 peak 的逐通道特征，不触发波形层读取。",
                parameters=(AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),),
                returns=(
                    "`list[dict]`；每项至少含 `board`、`channel`、`area`、`height`、"
                    "`merged_index`，并在聚合数据可用时含 `n_hits` 与 `area_fraction`。"
                ),
                notes=("空 peak 返回空列表。", "通道键始终应按 `(board, channel)` 解释。"),
                example="""channels = accessor.get_peak_channels(peak_id=919)
for channel in channels:
    print(channel["board"], channel["channel"], channel["area"])
""",
            ),
            AccessorMemberSpec(
                "get_channel_waveform",
                "按 hit-merged 行索引提取一个通道的波形窗口。",
                parameters=(
                    AccessorParameterSpec(
                        "merged_index", "`hit_merged` 的行索引，通常来自 `get_peak_channels()`。"
                    ),
                    AccessorParameterSpec("pad", "在 hit 边界两侧额外保留的采样点数。"),
                ),
                returns="包含 `waveform`、`time_ns`、`abs_time_ps`、`dt` 和通道信息的字典。",
                notes=("首次调用会加载波形层并缓存结果。",),
            ),
            AccessorMemberSpec(
                "get_peak_channel_data",
                "一次返回 peak 的通道特征，并可为每个通道附加波形。",
                parameters=(
                    AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),
                    AccessorParameterSpec("include_waveform", "为 `True` 时给结果项添加波形数据。"),
                    AccessorParameterSpec("pad", "请求波形时使用的边界扩展采样点数。"),
                ),
                returns="`list[dict]`；默认是特征项，启用 `include_waveform` 后同时包含波形字段。",
                notes=("波形读取成本更高；先用 `get_peak_channels()` 筛选通常更高效。",),
            ),
            AccessorMemberSpec(
                "clear_waveform_cache",
                "清空已提取的通道波形缓存，可选地释放原始波形层。",
                parameters=(
                    AccessorParameterSpec(
                        "release_wave_pool", "为 `True` 时同时释放已加载的 records/wave pool 层。"
                    ),
                ),
                returns="无返回值。",
            ),
            AccessorMemberSpec(
                "get_sum_waveform",
                "取得 peak 的求和波形及其时间信息。",
                parameters=(AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),),
                returns="求和波形字典；找不到对应 peak 时返回 `None`。",
            ),
            AccessorMemberSpec(
                "plot",
                "绘制 peak 的通道波形总览，并可叠加特征和命中窗口。",
                parameters=(
                    AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),
                    AccessorParameterSpec("pad", "通道波形窗口的边界扩展采样点数。"),
                    AccessorParameterSpec("figsize", "Matplotlib 图尺寸；`None` 使用默认布局。"),
                    AccessorParameterSpec("show_sum", "是否显示求和波形。"),
                    AccessorParameterSpec(
                        "show_features", "要标注的特征名称列表；`None` 使用默认项。"
                    ),
                    AccessorParameterSpec("show_hit_windows", "是否显示 hit 时间窗口。"),
                    AccessorParameterSpec("show_merged_index", "是否在图中标注 merged index。"),
                ),
                returns="`(figure, axes)`；未找到数据时元素可能为 `None`。",
                notes=("需要安装 Matplotlib。",),
            ),
            AccessorMemberSpec(
                "batch_plot",
                "将多个 peak 的通道图批量写入目录。",
                parameters=(
                    AccessorParameterSpec("peak_ids", "要绘制的 peak ID 列表。"),
                    AccessorParameterSpec("output_dir", "输出图像的目录。"),
                    AccessorParameterSpec("pad", "波形窗口的边界扩展采样点数。"),
                    AccessorParameterSpec("show_sum", "是否显示求和波形。"),
                    AccessorParameterSpec("show_features", "要标注的特征名称列表。"),
                    AccessorParameterSpec("show_hit_windows", "是否显示 hit 时间窗口。"),
                    AccessorParameterSpec("show_merged_index", "是否标注 merged index。"),
                ),
                returns="无返回值；图像写入 `output_dir`。",
                notes=("需要安装 Matplotlib，并确保输出目录可写。",),
            ),
            AccessorMemberSpec(
                "plot_channel_comparison",
                "将选定通道叠加到同一坐标轴，用于比较形状和相对时间。",
                parameters=(
                    AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),
                    AccessorParameterSpec(
                        "channel_selector", "要显示的通道选择器；`None` 表示全部通道。"
                    ),
                    AccessorParameterSpec("pad", "波形窗口的边界扩展采样点数。"),
                    AccessorParameterSpec("figsize", "Matplotlib 图尺寸。"),
                ),
                returns="`(figure, axes)`。",
                notes=("需要安装 Matplotlib。",),
            ),
            AccessorMemberSpec(
                "plot_sum_vs_channels",
                "对比求和波形与各通道波形。",
                parameters=(
                    AccessorParameterSpec("peak_id", "目标 peak 的整数 ID。"),
                    AccessorParameterSpec("pad", "波形窗口的边界扩展采样点数。"),
                    AccessorParameterSpec("figsize", "Matplotlib 图尺寸。"),
                ),
                returns="`(figure, axes)`。",
                notes=("需要安装 Matplotlib。",),
            ),
        ),
    ),
    AccessorDocumentationSpec(
        accessor_class=S1S2PairAccessor,
        slug="s1-s2-pair-accessor",
        summary="查询、筛选和绘制 S1-S2 配对，并按需加载 peak 波形。",
        introduction=(
            "S1S2PairAccessor 把 S1-S2 配对表、筛选条件、求和波形和位置重建聚合为只读查询接口。"
            "配对表与波形层独立延迟加载，可先在 structured array 上构建条件，再读取少量候选的波形。"
        ),
        purpose=(
            '用于定位 S1/S2 关系、漂移时间、质量标志与重建位置。默认 `source="pairs"` 读取最终选择结果；'
            '需要检查全部候选时改用 `source="candidates"`。'
        ),
        example="""from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor

accessor = S1S2PairAccessor(ctx, run_id="run_001", selected_only=True)
selected = accessor.filter_pairs(score_total_range=(0.8, 1.0))""",
        constructor_parameters=(
            AccessorParameterSpec("context", "已配置插件和数据存储的 Context。"),
            AccessorParameterSpec("run_id", "本次查询对应的 run ID。"),
            AccessorParameterSpec(
                "source", '`"pairs"` 读取最终配对；`"candidates"` 读取所有候选配对。'
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
                "get_pair",
                "按 pair ID 返回一个完整 structured row。",
                parameters=(AccessorParameterSpec("pair_id", "目标配对的整数 ID。"),),
                returns="匹配的 `np.void` row；找不到时返回 `None`。",
            ),
            AccessorMemberSpec(
                "get_pairs_for_s1",
                "返回指定 S1 关联的全部配对。",
                parameters=(AccessorParameterSpec("s1_peak_id", "S1 peak 的整数 ID。"),),
                returns="保留原 dtype 的 structured array；无匹配时为空数组。",
            ),
            AccessorMemberSpec(
                "get_pairs_for_s2",
                "返回指定 S2 关联的全部配对。",
                parameters=(AccessorParameterSpec("s2_peak_id", "S2 peak 的整数 ID。"),),
                returns="保留原 dtype 的 structured array；无匹配时为空数组。",
            ),
            AccessorMemberSpec(
                "build_mask",
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
                example="""mask = accessor.build_mask(
    drift_time_ns_range=(10_000, 50_000),
    score_total_range=(0.8, None),
    selected=True,
)
candidate_pairs = accessor.pairs[mask]
""",
            ),
            AccessorMemberSpec(
                "filter_pairs",
                "`build_mask()` 的快捷封装，直接返回筛选后的配对。",
                parameters=(
                    AccessorParameterSpec("kwargs", "传递给 `build_mask()` 的具名筛选参数。"),
                ),
                returns="筛选后的 structured array。",
                notes=("只接受 `build_mask()` 支持的关键字参数。",),
            ),
            AccessorMemberSpec(
                "get_waveform",
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
                "get_pair_waveforms",
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
            AccessorMemberSpec(
                "clear_waveform_cache", "清空已提取的 waveform 缓存。", returns="无返回值。"
            ),
            AccessorMemberSpec(
                "release_waveform_layer",
                "释放原始波形层和缓存，下一次波形查询会重新加载。",
                returns="无返回值。",
            ),
            AccessorMemberSpec(
                "plot_pair",
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
                "get_positions",
                "返回与当前配对范围对应的位置重建数据。",
                returns="`np.ndarray` structured array；位置数据不存在时返回正确 dtype 的空数组。",
                notes=("`selected_only=True` 时结果也会按当前配对集合过滤。",),
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
    """Escape prose first, then render its restricted backtick code notation."""
    escaped = str(escape(value))
    return Markup(re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped))


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
                members.append(
                    AccessorMemberView(
                        name=member_spec.name,
                        kind=member_spec.kind,
                        signature=str(signature),
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
                )
            )
        return views

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

    def generate(self, output_dir: Path) -> dict[str, Path]:
        output_dir = Path(output_dir)
        self.plugin_generator.load_builtin_plugins()
        generated = self.plugin_generator.generate_web(
            output_dir,
            index_relative_path="plugins/index.html",
            plugin_relative_dir="plugins",
            asset_relative_dir="assets",
            site_home_href="index.html",
            accessor_relative_path="accessors/index.html",
        )
        views = self.build_accessor_views()
        env = self.plugin_generator._get_web_jinja_env()
        env.filters["inline_code"] = _inline_code
        accessor_dir = output_dir / "accessors"
        accessor_dir.mkdir(parents=True, exist_ok=True)
        home_path = output_dir / "index.html"
        home_path.write_text(env.get_template("web/site_index.html.j2").render(), encoding="utf-8")
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
        return generated
