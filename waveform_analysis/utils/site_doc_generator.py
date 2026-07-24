"""Internal generator for the offline WaveformAnalysis documentation site."""

from dataclasses import dataclass
import inspect
from pathlib import Path
from typing import Any

from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor
from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator
from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor


@dataclass(frozen=True)
class AccessorMemberSpec:
    name: str
    description: str
    kind: str = "method"


@dataclass(frozen=True)
class AccessorDocumentationSpec:
    accessor_class: type
    slug: str
    summary: str
    purpose: str
    example: str
    members: tuple[AccessorMemberSpec, ...]


@dataclass(frozen=True)
class AccessorMemberView:
    name: str
    kind: str
    signature: str
    description: str


@dataclass(frozen=True)
class AccessorDocumentationView:
    name: str
    slug: str
    module_path: str
    summary: str
    purpose: str
    example: str
    constructor_signature: str
    members: tuple[AccessorMemberView, ...]


ACCESSOR_DOCUMENTATION_REGISTRY = (
    AccessorDocumentationSpec(
        accessor_class=PeakChannelAccessor,
        slug="peak-channel-accessor",
        summary="按 peak 查询各硬件通道的特征与波形，并提供常用对比绘图。",
        purpose="用于从 peak 视角下钻到唯一键 (board, channel)，检查通道贡献和波形形态。",
        example="""from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(ctx, "run_001")
channels = accessor.get_peak_channels(peak_id=919)""",
        members=(
            AccessorMemberSpec("get_peak_channels", "返回指定 peak 的逐通道特征。"),
            AccessorMemberSpec("get_channel_waveform", "按 merged index 提取单通道波形。"),
            AccessorMemberSpec("get_peak_channel_data", "组合逐通道特征与可选波形。"),
            AccessorMemberSpec("clear_waveform_cache", "清理已缓存的通道波形。"),
            AccessorMemberSpec("get_sum_waveform", "返回指定 peak 的求和波形。"),
            AccessorMemberSpec("plot", "绘制 peak 的通道波形总览。"),
            AccessorMemberSpec("batch_plot", "批量生成多个 peak 的图。"),
            AccessorMemberSpec("plot_channel_comparison", "叠加多个通道进行比较。"),
            AccessorMemberSpec("plot_sum_vs_channels", "比较求和波形与各通道波形。"),
        ),
    ),
    AccessorDocumentationSpec(
        accessor_class=S1S2PairAccessor,
        slug="s1-s2-pair-accessor",
        summary="查询、筛选和绘制 S1-S2 配对，并按需加载 peak 波形。",
        purpose="用于从配对结果快速定位 S1/S2 关系、质量条件、波形和重建位置。",
        example="""from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor

accessor = S1S2PairAccessor(ctx, "run_001")
selected = accessor.filter_pairs(score_total_range=(0.8, 1.0))""",
        members=(
            AccessorMemberSpec("pairs", "访问全部配对 structured array。", "property"),
            AccessorMemberSpec("get_pair", "按 pair_id 返回单个配对。"),
            AccessorMemberSpec("get_pairs_for_s1", "返回指定 S1 的全部配对。"),
            AccessorMemberSpec("get_pairs_for_s2", "返回指定 S2 的全部配对。"),
            AccessorMemberSpec("build_mask", "按物理量、标志位或自定义条件构建掩码。"),
            AccessorMemberSpec("filter_pairs", "使用筛选参数直接返回配对。"),
            AccessorMemberSpec("get_waveform", "按 peak_id 获取求和波形。"),
            AccessorMemberSpec("get_pair_waveforms", "获取一个配对的 S1 和 S2 波形。"),
            AccessorMemberSpec("clear_waveform_cache", "清理已提取的波形缓存。"),
            AccessorMemberSpec("release_waveform_layer", "释放延迟加载的完整波形层。"),
            AccessorMemberSpec("plot_pair", "在统一时间轴上绘制一个配对。"),
            AccessorMemberSpec("get_positions", "返回位置重建数据。"),
        ),
    ),
)


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
                members.append(
                    AccessorMemberView(
                        name=member_spec.name,
                        kind=member_spec.kind,
                        signature=str(inspect.signature(target)),
                        description=member_spec.description,
                    )
                )
            views.append(
                AccessorDocumentationView(
                    name=spec.accessor_class.__name__,
                    slug=spec.slug,
                    module_path=spec.accessor_class.__module__,
                    summary=spec.summary,
                    purpose=spec.purpose,
                    example=spec.example,
                    constructor_signature=str(inspect.signature(spec.accessor_class)),
                    members=tuple(members),
                )
            )
        return views

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
