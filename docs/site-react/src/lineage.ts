export type PortData = {
  id: string;
  name: string;
  kind: "in" | "out";
  dtype: string;
  index: number;
  color: string;
};

export type GraphNodeData = {
  id: string;
  label: string;
  pluginClass: string;
  summary: string;
  href: string;
  kind: string;
  isLineageVirtual: boolean;
  pluginSet: string;
  colors: { background: string; border: string; header: string };
  in_ports: PortData[];
  out_ports: PortData[];
  width: number;
  height: number;
  documentationCompleteness: number;
  dagImpact: number;
};

export type GraphNode = { data: GraphNodeData };

export type GraphEdgeData = {
  id: string;
  source_node_id: string;
  source_port_id: string;
  target_node_id: string;
  target_port_id: string;
  dtype: string;
  category: string;
  kind: string;
  style: { color: string; width: number; alpha: number; dash: string };
};

export type GraphEdge = { data: GraphEdgeData };

export type Graph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  views: Record<string, string[]>;
  relations: Record<string, { inputs: string[]; consumers: string[] }>;
  focusDepth: number;
};

export type Point = { x: number; y: number };
export type ElkSection = {
  startPoint: Point;
  bendPoints?: Point[];
  endPoint: Point;
};

export const LINEAGE_LAYOUT_OPTIONS = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.edgeRouting": "ORTHOGONAL",
  // In a RIGHT-oriented layered graph this controls the vertical separation
  // of sibling nodes within the same layer.
  "elk.spacing.nodeNode": "80",
  "elk.spacing.edgeNode": "16",
  "elk.layered.spacing.nodeNodeBetweenLayers": "78",
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
  "elk.layered.mergeEdges": "true",
  "elk.layered.nodePlacement.favorStraightEdges": "true",
  "elk.layered.unnecessaryBendpoints": "true",
  // Network simplex keeps the declared main chain on a shared horizontal
  // backbone.  Branches leave that backbone only when they need to reach a
  // different port row, which avoids repeated bends through intermediate layers.
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.layered.nodePlacement.networkSimplex.nodeFlexibility": "100",
} as const;

export function normalizeView(value: string | null): "overview" | "full" {
  return value === "full" || value === "all" ? "full" : "overview";
}

export function visibleGraph(graph: Graph, view: string, focus = "") {
  const normalized = normalizeView(view);
  const focusRelation = focus ? graph.relations[focus] : undefined;
  const visible = view === "focus" && focusRelation
    ? new Set([focus, ...focusRelation.inputs, ...focusRelation.consumers])
    : new Set(graph.views[normalized] ?? graph.views.overview ?? []);
  return {
    nodes: graph.nodes.filter((node) => visible.has(node.data.id)),
    edges: graph.edges.filter(
      (edge) =>
        visible.has(edge.data.source_node_id) && visible.has(edge.data.target_node_id),
    ),
  };
}

export function edgeHandleMapping(edge: GraphEdgeData) {
  return {
    source: edge.source_node_id,
    sourceHandle: edge.source_port_id,
    target: edge.target_node_id,
    targetHandle: edge.target_port_id,
  };
}

export function orthogonalPoints(sections: ElkSection[] | undefined): Point[] | null {
  if (!sections?.length) return null;
  const points: Point[] = [];
  sections.forEach((section, sectionIndex) => {
    const sectionPoints = compactOrthogonalPoints([
      section.startPoint,
      ...(section.bendPoints ?? []),
      section.endPoint,
    ]);
    sectionPoints.forEach((point, pointIndex) => {
      const previous = points.at(-1);
      if (sectionIndex && pointIndex === 0 && previous?.x === point.x && previous.y === point.y) return;
      points.push(point);
    });
  });
  return points;
}

export function orthogonalPath(sections: ElkSection[] | undefined): string | null {
  const points = orthogonalPoints(sections);
  return points?.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ") ?? null;
}

function compactOrthogonalPoints(points: Point[]) {
  const compact: Point[] = [];
  points.forEach((point) => {
    const previous = compact.at(-1);
    if (previous?.x === point.x && previous.y === point.y) return;
    const beforePrevious = compact.at(-2);
    if (beforePrevious && previous && (
      (beforePrevious.x === previous.x && previous.x === point.x)
      || (beforePrevious.y === previous.y && previous.y === point.y)
    )) {
      compact[compact.length - 1] = point;
      return;
    }
    compact.push(point);
  });
  return compact;
}

export function invalidConnections(graph: Graph) {
  const nodes = new Map(graph.nodes.map((node) => [node.data.id, node.data]));
  const ports = new Map<string, { node: string; kind: "in" | "out" }>();
  graph.nodes.forEach((node) => {
    node.data.in_ports.forEach((port) => ports.set(port.id, { node: node.data.id, kind: "in" }));
    node.data.out_ports.forEach((port) => ports.set(port.id, { node: node.data.id, kind: "out" }));
  });
  return graph.edges.filter((entry) => {
    const edge = entry.data;
    const source = ports.get(edge.source_port_id);
    const target = ports.get(edge.target_port_id);
    return !nodes.has(edge.source_node_id)
      || !nodes.has(edge.target_node_id)
      || source?.node !== edge.source_node_id
      || source.kind !== "out"
      || target?.node !== edge.target_node_id
      || target.kind !== "in";
  });
}

function relationsFor(nodes: GraphNode[], edges: GraphEdge[]): Graph["relations"] {
  const relations: Graph["relations"] = {};
  nodes.forEach((node) => {
    relations[node.data.id] = { inputs: [], consumers: [] };
  });
  edges.forEach(({ data }) => {
    const source = relations[data.source_node_id];
    const target = relations[data.target_node_id];
    if (!source || !target) return;
    if (!source.consumers.includes(data.target_node_id)) {
      source.consumers.push(data.target_node_id);
    }
    if (!target.inputs.includes(data.source_node_id)) {
      target.inputs.push(data.source_node_id);
    }
  });
  return relations;
}

/**
 * Removes calculation-only nodes and their attached edges from the browser
 * view. Hiding is strictly presentational: it must never create a dependency
 * between real plugins that the original DAG did not declare.
 */
export function withoutVirtualNodes(graph: Graph): Graph {
  const virtualIds = new Set(
    graph.nodes
      .filter((node) => node.data.isLineageVirtual)
      .map((node) => node.data.id),
  );
  if (!virtualIds.size) return graph;

  const nodes = graph.nodes.filter((node) => !virtualIds.has(node.data.id));
  const ids = new Set(nodes.map((node) => node.data.id));
  const finalEdges = graph.edges.filter(
    (edge) => ids.has(edge.data.source_node_id) && ids.has(edge.data.target_node_id),
  );
  return {
    ...graph,
    nodes,
    edges: finalEdges,
    views: Object.fromEntries(
      Object.entries(graph.views).map(([name, viewIds]) => [
        name,
        viewIds.filter((id) => ids.has(id)),
      ]),
    ),
    relations: relationsFor(nodes, finalEdges),
  };
}
