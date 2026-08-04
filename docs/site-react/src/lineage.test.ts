import assert from "node:assert/strict";
import test from "node:test";
import {
  edgeHandleMapping,
  invalidConnections,
  LINEAGE_LAYOUT_OPTIONS,
  normalizeView,
  orthogonalPoints,
  orthogonalPath,
  withoutVirtualNodes,
  visibleGraph,
  type Graph,
} from "./lineage.js";

const graph: Graph = {
  nodes: [
    { data: { id: "a", label: "a", pluginClass: "A", summary: "source", href: "a.html", kind: "raw_data", isLineageVirtual: false, pluginSet: "io", colors: { background: "#fff", border: "#000", header: "#eee" }, in_ports: [], out_ports: [{ id: "OUT::a::0", name: "a", kind: "out", dtype: "array", index: 0, color: "#123" }], width: 248, height: 106, documentationCompleteness: 100, dagImpact: 50 } },
    { data: { id: "b", label: "b", pluginClass: "B", summary: "target", href: "b.html", kind: "intermediate", isLineageVirtual: false, pluginSet: "hit", colors: { background: "#fff", border: "#000", header: "#eee" }, in_ports: [{ id: "IN::b::0", name: "a", kind: "in", dtype: "array", index: 0, color: "#123" }], out_ports: [{ id: "OUT::b::0", name: "b", kind: "out", dtype: "array", index: 0, color: "#123" }], width: 248, height: 106, documentationCompleteness: 100, dagImpact: 25 } },
  ],
  edges: [{ data: { id: "a-b", source_node_id: "a", source_port_id: "OUT::a::0", target_node_id: "b", target_port_id: "IN::b::0", dtype: "array", category: "array", kind: "main", style: { color: "#123", width: 2, alpha: 1, dash: "solid" } } }],
  views: { overview: ["a", "b"], full: ["a", "b"] },
  relations: { a: { inputs: [], consumers: ["b"] }, b: { inputs: ["a"], consumers: [] } },
  focusDepth: 2,
};

test("view aliases preserve existing core/all URLs", () => {
  assert.equal(normalizeView("core"), "overview");
  assert.equal(normalizeView("all"), "full");
});

test("layered layout keeps the main chain on a horizontal backbone", () => {
  assert.equal(LINEAGE_LAYOUT_OPTIONS["elk.direction"], "RIGHT");
  assert.equal(LINEAGE_LAYOUT_OPTIONS["elk.layered.nodePlacement.strategy"], "NETWORK_SIMPLEX");
  assert.equal(LINEAGE_LAYOUT_OPTIONS["elk.layered.nodePlacement.networkSimplex.nodeFlexibility"], "100");
  assert.equal(LINEAGE_LAYOUT_OPTIONS["elk.spacing.nodeNode"], "80");
  assert.equal(LINEAGE_LAYOUT_OPTIONS["elk.layered.mergeEdges"], "true");
  assert.equal(LINEAGE_LAYOUT_OPTIONS["elk.layered.nodePlacement.favorStraightEdges"], "true");
  assert.equal(LINEAGE_LAYOUT_OPTIONS["elk.layered.unnecessaryBendpoints"], "true");
  assert.equal(
    "elk.layered.considerModelOrder.strategy" in LINEAGE_LAYOUT_OPTIONS,
    false,
  );
});

test("visible graph conserves every port-level edge", () => {
  const visible = visibleGraph(graph, "core");
  assert.equal(visible.edges.length, graph.edges.length);
  assert.deepEqual(edgeHandleMapping(visible.edges[0].data), {
    source: "a", sourceHandle: "OUT::a::0", target: "b", targetHandle: "IN::b::0",
  });
  assert.deepEqual(invalidConnections(graph), []);
  assert.deepEqual(visibleGraph(graph, "focus", "b").nodes.map((node) => node.data.id), ["a", "b"]);
});

test("ELK sections become an orthogonal path and missing sections request fallback", () => {
  assert.equal(orthogonalPath(undefined), null);
  assert.deepEqual(orthogonalPoints([{ startPoint: { x: 1, y: 2 }, bendPoints: [{ x: 3, y: 2 }], endPoint: { x: 3, y: 4 } }]), [{ x: 1, y: 2 }, { x: 3, y: 2 }, { x: 3, y: 4 }]);
  assert.equal(orthogonalPath([{ startPoint: { x: 1, y: 2 }, bendPoints: [{ x: 3, y: 2 }], endPoint: { x: 3, y: 4 } }]), "M 1 2 L 3 2 L 3 4");
  assert.equal(orthogonalPath([{ startPoint: { x: 1, y: 2 }, bendPoints: [{ x: 3, y: 2 }, { x: 5, y: 2 }], endPoint: { x: 5, y: 4 } }]), "M 1 2 L 5 2 L 5 4");
});

test("hiding virtual nodes removes their edges without creating a bypass", () => {
  const virtualGraph: Graph = {
    ...graph,
    nodes: [
      graph.nodes[0],
      { data: { id: "virtual", label: "virtual", pluginClass: "Virtual", summary: "helper", href: "virtual.html", kind: "intermediate", isLineageVirtual: true, pluginSet: "other", colors: { background: "#fff", border: "#000", header: "#eee" }, in_ports: [{ id: "IN::virtual::0", name: "a", kind: "in", dtype: "array", index: 0, color: "#123" }], out_ports: [{ id: "OUT::virtual::0", name: "virtual", kind: "out", dtype: "array", index: 0, color: "#123" }], width: 248, height: 106, documentationCompleteness: 100, dagImpact: 0 } },
      graph.nodes[1],
    ],
    edges: [
      { data: { ...graph.edges[0].data, id: "a-virtual", target_node_id: "virtual", target_port_id: "IN::virtual::0" } },
      { data: { ...graph.edges[0].data, id: "virtual-b", source_node_id: "virtual", source_port_id: "OUT::virtual::0" } },
    ],
    views: { overview: ["a", "virtual", "b"], full: ["a", "virtual", "b"] },
    relations: { a: { inputs: [], consumers: ["virtual"] }, virtual: { inputs: ["a"], consumers: ["b"] }, b: { inputs: ["virtual"], consumers: [] } },
  };
  const collapsed = withoutVirtualNodes(virtualGraph);

  assert.deepEqual(collapsed.nodes.map((node) => node.data.id), ["a", "b"]);
  assert.deepEqual(collapsed.edges, []);
  assert.deepEqual(collapsed.relations, { a: { inputs: [], consumers: [] }, b: { inputs: [], consumers: [] } });
});

test("hiding a multi-input virtual node preserves only declared real edges", () => {
  const multiVirtualGraph: Graph = {
    ...graph,
    nodes: [
      ...graph.nodes,
      { data: { ...graph.nodes[0].data, id: "c", label: "c", pluginClass: "C", out_ports: [{ id: "OUT::c::0", name: "c", kind: "out", dtype: "array", index: 0, color: "#123" }] } },
      { data: { id: "virtual", label: "virtual", pluginClass: "Virtual", summary: "helper", href: "virtual.html", kind: "intermediate", isLineageVirtual: true, pluginSet: "other", colors: { background: "#fff", border: "#000", header: "#eee" }, in_ports: [{ id: "IN::virtual::0", name: "a", kind: "in", dtype: "array", index: 0, color: "#123" }, { id: "IN::virtual::1", name: "c", kind: "in", dtype: "array", index: 1, color: "#123" }], out_ports: [{ id: "OUT::virtual::0", name: "virtual", kind: "out", dtype: "array", index: 0, color: "#123" }], width: 248, height: 134, documentationCompleteness: 100, dagImpact: 0 } },
    ],
    edges: [
      graph.edges[0],
      { data: { ...graph.edges[0].data, id: "a-virtual", target_node_id: "virtual", target_port_id: "IN::virtual::0" } },
      { data: { ...graph.edges[0].data, id: "c-virtual", source_node_id: "c", source_port_id: "OUT::c::0", target_node_id: "virtual", target_port_id: "IN::virtual::1" } },
      { data: { ...graph.edges[0].data, id: "virtual-b", source_node_id: "virtual", source_port_id: "OUT::virtual::0" } },
    ],
    views: { overview: ["a", "b", "c", "virtual"], full: ["a", "b", "c", "virtual"] },
    relations: { a: { inputs: [], consumers: ["b", "virtual"] }, b: { inputs: ["a", "virtual"], consumers: [] }, c: { inputs: [], consumers: ["virtual"] }, virtual: { inputs: ["a", "c"], consumers: ["b"] } },
  };
  const collapsed = withoutVirtualNodes(multiVirtualGraph);

  assert.deepEqual(collapsed.edges.map((edge) => edge.data.id), ["a-b"]);
  assert.deepEqual(collapsed.relations, {
    a: { inputs: [], consumers: ["b"] },
    b: { inputs: ["a"], consumers: [] },
    c: { inputs: [], consumers: [] },
  });
});
