"""
Model 模块测试
"""

import pytest

from waveform_analysis.core.foundation.model import (
    EdgeModel,
    LineageGraphModel,
    NodeModel,
    PortModel,
    build_lineage_graph,
)


class TestPortModel:
    """PortModel 测试"""

    def test_port_creation(self):
        """测试端口创建"""
        port = PortModel(
            id="port_1",
            name="input",
            kind="in",
            dtype="int64",
            parent_node_id="node_1",
            index=0,
        )

        assert port.id == "port_1"
        assert port.name == "input"
        assert port.kind == "in"
        assert port.dtype == "int64"
        assert port.parent_node_id == "node_1"
        assert port.index == 0


class TestNodeModel:
    """NodeModel 测试"""

    def test_node_creation_minimal(self):
        """测试节点最小创建"""
        node = NodeModel(
            id="node_1",
            key="raw_data",
            title="Raw Data",
            plugin_class="RawDataPlugin",
        )

        assert node.id == "node_1"
        assert node.key == "raw_data"
        assert node.title == "Raw Data"
        assert node.plugin_class == "RawDataPlugin"
        assert node.description == ""
        assert node.config == {}
        assert node.in_ports == []
        assert node.out_ports == []
        assert node.depth == 0

    def test_node_creation_full(self):
        """测试节点完整创建"""
        in_port = PortModel("p1", "in", "in", "int64", "node_1", 0)
        out_port = PortModel("p2", "out", "out", "float64", "node_1", 0)

        node = NodeModel(
            id="node_1",
            key="processor",
            title="Processor",
            plugin_class="ProcessorPlugin",
            description="A processing node",
            config={"param": 10},
            in_ports=[in_port],
            out_ports=[out_port],
            depth=2,
        )

        assert node.description == "A processing node"
        assert node.config["param"] == 10
        assert len(node.in_ports) == 1
        assert len(node.out_ports) == 1
        assert node.depth == 2


class TestEdgeModel:
    """EdgeModel 测试"""

    def test_edge_creation(self):
        """测试边创建"""
        edge = EdgeModel(
            source_node_id="node_1",
            source_port_id="out_port",
            target_node_id="node_2",
            target_port_id="in_port",
            dtype="float64",
        )

        assert edge.source_node_id == "node_1"
        assert edge.source_port_id == "out_port"
        assert edge.target_node_id == "node_2"
        assert edge.target_port_id == "in_port"
        assert edge.dtype == "float64"

    def test_edge_default_dtype(self):
        """测试边的默认 dtype"""
        edge = EdgeModel(
            source_node_id="n1",
            source_port_id="p1",
            target_node_id="n2",
            target_port_id="p2",
        )
        assert edge.dtype == "unknown"


class TestLineageGraphModel:
    """LineageGraphModel 测试"""

    def test_empty_graph(self):
        """测试空图"""
        graph = LineageGraphModel()

        assert graph.nodes == {}
        assert graph.edges == []
        assert graph.metadata == {}

    def test_graph_with_nodes(self):
        """测试包含节点的图"""
        node1 = NodeModel("n1", "k1", "Node 1", "Plugin1")
        node2 = NodeModel("n2", "k2", "Node 2", "Plugin2")

        graph = LineageGraphModel(
            nodes={"n1": node1, "n2": node2},
            edges=[],
            metadata={"version": "1.0"},
        )

        assert len(graph.nodes) == 2
        assert "n1" in graph.nodes
        assert graph.metadata["version"] == "1.0"

    def test_to_mermaid_empty(self):
        """测试空图的 Mermaid 输出"""
        graph = LineageGraphModel()
        mermaid = graph.to_mermaid()

        assert "graph LR" in mermaid

    def test_to_mermaid_with_nodes_and_edges(self):
        """测试有节点和边的 Mermaid 输出"""
        node1 = NodeModel("node1", "key1", "Title 1", "Plugin1")
        node2 = NodeModel("node2", "key2", "Title 2", "Plugin2")
        edge = EdgeModel("node1", "out", "node2", "in", "int64")

        graph = LineageGraphModel(
            nodes={"node1": node1, "node2": node2},
            edges=[edge],
        )

        mermaid = graph.to_mermaid()

        assert "graph LR" in mermaid
        assert "Title 1" in mermaid
        assert "Title 2" in mermaid
        assert "int64" in mermaid
        assert "-->" in mermaid

    def test_to_mermaid_special_chars(self):
        """测试特殊字符的处理"""
        node = NodeModel("node[1].test", "key", "Title", "Plugin")
        graph = LineageGraphModel(nodes={"node[1].test": node})

        mermaid = graph.to_mermaid()

        # 特殊字符应该被替换
        assert "node_1__test" in mermaid


class TestBuildLineageGraph:
    """build_lineage_graph 函数测试"""

    def test_build_empty_lineage(self):
        """测试构建空血缘图"""
        lineage = {}
        graph = build_lineage_graph(lineage, "target")

        assert isinstance(graph, LineageGraphModel)

    def test_build_simple_lineage(self):
        """测试构建简单血缘图"""
        lineage = {
            "raw_data": {
                "provides": "raw_data",
                "version": "1.0",
                "depends_on": [],
                "options": {},
            }
        }

        # Mock plugins dict
        class MockPlugin:
            provides = "raw_data"
            version = "1.0"
            dtype = None

        plugins = {"raw_data": MockPlugin()}

        graph = build_lineage_graph(lineage, "raw_data", plugins)

        assert isinstance(graph, LineageGraphModel)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
