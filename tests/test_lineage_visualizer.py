from waveform_analysis.core.foundation.model import (
    EdgeModel,
    LineageGraphModel,
    NodeModel,
    PortModel,
)
from waveform_analysis.core.foundation.utils import LineageStyle
from waveform_analysis.utils.visualization.lineage_visualizer import (
    _layout_nodes_source_to_target,
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

    reordered = _reorder_layers(layers, edges, y_gap=1.0, iterations=1)

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

    plot_lineage_plotly(model, "waveforms", style=LineageStyle(layout_reorder=False))

    assert shown == [True]
