from waveform_analysis.core.foundation.model import (
    EdgeModel,
    LineageGraphModel,
    NodeModel,
    PortModel,
)
from waveform_analysis.core.foundation.utils import LineageStyle
from waveform_analysis.utils.visualization.lineage_visualizer import (
    _layout_nodes_source_to_target,
    _node_heights_for,
    _reorder_layers,
    plot_lineage_plotly,
)


def test_layout_places_sources_left_of_targets():
    source = NodeModel(
        id="raw_files",
        key="raw_files",
        title="Raw Files",
        plugin_class="RawFilesPlugin",
        out_ports=[
            PortModel(
                id="OUT::raw_files::0",
                name="raw_files",
                kind="out",
                dtype="List[List[str]]",
                parent_node_id="raw_files",
                index=0,
            )
        ],
        depth=0,
    )
    target = NodeModel(
        id="waveforms",
        key="waveforms",
        title="Waveforms",
        plugin_class="WaveformsPlugin",
        in_ports=[
            PortModel(
                id="IN::waveforms::0",
                name="raw_files",
                kind="in",
                dtype="List[List[str]]",
                parent_node_id="waveforms",
                index=0,
            )
        ],
        out_ports=[
            PortModel(
                id="OUT::waveforms::0",
                name="waveforms",
                kind="out",
                dtype="List[np.ndarray]",
                parent_node_id="waveforms",
                index=0,
            )
        ],
        depth=1,
    )
    model = LineageGraphModel(
        nodes={"raw_files": source, "waveforms": target},
        edges=[
            EdgeModel(
                source_node_id="raw_files",
                source_port_id="OUT::raw_files::0",
                target_node_id="waveforms",
                target_port_id="IN::waveforms::0",
                dtype="List[List[str]]",
            )
        ],
    )

    pos = _layout_nodes_source_to_target(model, LineageStyle(layout_reorder=False))

    assert pos["raw_files"][0] < pos["waveforms"][0]
    assert pos["OUT::raw_files::0"][0] < pos["IN::waveforms::0"][0]


def test_reorder_layers_uses_upstream_neighbors_for_forward_pass():
    edges = [
        EdgeModel(
            source_node_id="source_a",
            source_port_id="OUT::source_a::0",
            target_node_id="target_a",
            target_port_id="IN::target_a::0",
        ),
        EdgeModel(
            source_node_id="source_b",
            source_port_id="OUT::source_b::0",
            target_node_id="target_b",
            target_port_id="IN::target_b::0",
        ),
    ]
    layers = {
        0: ["source_a", "source_b"],
        1: ["target_b", "target_a"],
    }

    style = LineageStyle(y_gap=1.0)
    reordered = _reorder_layers(
        layers,
        edges,
        node_heights={"source_a": 2.0, "source_b": 2.0, "target_a": 2.0, "target_b": 2.0},
        style=style,
        iterations=1,
    )

    assert reordered[1] == ["target_a", "target_b"]


def test_plotly_lineage_handles_adaptive_layout_without_max_depth_name_error(monkeypatch):
    import plotly.graph_objects as go

    shown = []
    monkeypatch.setattr(go.Figure, "show", lambda self: shown.append(True))

    source = NodeModel(
        id="raw_files",
        key="raw_files",
        title="Raw Files",
        plugin_class="RawFilesPlugin",
        out_ports=[
            PortModel(
                id="OUT::raw_files::0",
                name="raw_files",
                kind="out",
                dtype="List[List[str]]",
                parent_node_id="raw_files",
                index=0,
            )
        ],
        depth=0,
    )
    target = NodeModel(
        id="waveforms",
        key="waveforms",
        title="Waveforms",
        plugin_class="WaveformsPlugin",
        in_ports=[
            PortModel(
                id="IN::waveforms::0",
                name="raw_files",
                kind="in",
                dtype="List[List[str]]",
                parent_node_id="waveforms",
                index=0,
            )
        ],
        out_ports=[
            PortModel(
                id="OUT::waveforms::0",
                name="waveforms",
                kind="out",
                dtype="List[np.ndarray]",
                parent_node_id="waveforms",
                index=0,
            )
        ],
        depth=1,
    )
    model = LineageGraphModel(
        nodes={"raw_files": source, "waveforms": target},
        edges=[
            EdgeModel(
                source_node_id="raw_files",
                source_port_id="OUT::raw_files::0",
                target_node_id="waveforms",
                target_port_id="IN::waveforms::0",
                dtype="List[List[str]]",
            )
        ],
    )

    figure = plot_lineage_plotly(model, "waveforms", style=LineageStyle(layout_reorder=False))

    assert shown == [True]
    assert figure.layout.title.text == "Data Lineage: waveforms"


def test_layout_keeps_many_ports_inside_their_node_and_separates_tall_nodes():
    source_ids = [f"source_{index}" for index in range(8)]
    sources = {
        source_id: NodeModel(
            id=source_id,
            key=source_id,
            title=source_id,
            plugin_class="SourcePlugin",
            out_ports=[
                PortModel(
                    id=f"OUT::{source_id}::0",
                    name=source_id,
                    kind="out",
                    dtype="np.ndarray",
                    parent_node_id=source_id,
                    index=0,
                )
            ],
            depth=0,
        )
        for source_id in source_ids
    }
    target = NodeModel(
        id="target",
        key="target",
        title="Target",
        plugin_class="TargetPlugin",
        in_ports=[
            PortModel(
                id=f"IN::target::{index}",
                name=source_id,
                kind="in",
                dtype="np.ndarray",
                parent_node_id="target",
                index=index,
            )
            for index, source_id in enumerate(source_ids)
        ],
        depth=1,
    )
    sibling = NodeModel(
        id="sibling",
        key="sibling",
        title="Sibling",
        plugin_class="TargetPlugin",
        depth=1,
    )
    edges = [
        EdgeModel(
            source_node_id=source_id,
            source_port_id=f"OUT::{source_id}::0",
            target_node_id="target",
            target_port_id=f"IN::target::{index}",
            dtype="np.ndarray",
        )
        for index, source_id in enumerate(source_ids)
    ]
    model = LineageGraphModel(nodes={**sources, "target": target, "sibling": sibling}, edges=edges)
    style = LineageStyle(layout_reorder=False)

    heights = _node_heights_for(model, style)
    pos = _layout_nodes_source_to_target(model, style, heights)

    target_y = pos["target"][1]
    target_half_height = heights["target"] / 2
    for port in target.in_ports:
        assert target_y - target_half_height <= pos[port.id][1] <= target_y + target_half_height

    sibling_y = pos["sibling"][1]
    sibling_half_height = heights["sibling"] / 2
    assert abs(target_y - sibling_y) >= target_half_height + sibling_half_height
