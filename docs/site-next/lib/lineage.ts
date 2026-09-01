import type { LineageEdge, LineageModel, LineageNode } from "./site-model";

const STRUCTURED_FIELD_PATTERN = /\('[^']+',\s*'[^']+'\)/g;

export function dtypeSummary(dtype: string) {
  const value = dtype.trim();
  if (!value) return "array";
  const fields = value.match(STRUCTURED_FIELD_PATTERN)?.length ?? 0;
  if (fields) return `${fields} fields`;
  if (value.length <= 18) return value;
  return "structured dtype";
}

export type LineageGraph = { nodes: LineageNode[]; edges: LineageEdge[] };

function relationFor(model: LineageModel, id: string) {
  return {
    inputs: model.edges.filter((edge) => edge.target === id).map((edge) => edge.source),
    consumers: model.edges.filter((edge) => edge.source === id).map((edge) => edge.target),
  };
}

export function visibleGraph(model: LineageModel, view: "overview" | "full" = "overview", focus = ""): LineageGraph {
  const relation = focus && model.nodes.some((node) => node.id === focus) ? relationFor(model, focus) : undefined;
  const ids = relation ? new Set([focus, ...relation.inputs, ...relation.consumers]) : new Set(model.views[view] ?? model.views.overview);
  return { nodes: model.nodes.filter((node) => ids.has(node.id)), edges: model.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)) };
}

export function edgeHandleMapping(edge: LineageEdge) {
  return { source: edge.source, sourceHandle: edge.sourcePort, target: edge.target, targetHandle: edge.targetPort };
}

export type Point = { x: number; y: number };
export type LayoutSection = { startPoint: Point; bendPoints?: Point[]; endPoint: Point };

export function orthogonalPoints(sections: LayoutSection[] | undefined): Point[] | null {
  if (!sections?.length) return null;
  const points: Point[] = [];
  sections.forEach((section, sectionIndex) => {
    const current = [section.startPoint, ...(section.bendPoints ?? []), section.endPoint];
    current.forEach((point, pointIndex) => {
      const previous = points.at(-1);
      if (sectionIndex > 0 && pointIndex === 0 && previous?.x === point.x && previous.y === point.y) return;
      const before = points.at(-2);
      if (before && previous && ((before.x === previous.x && previous.x === point.x) || (before.y === previous.y && previous.y === point.y))) points[points.length - 1] = point;
      else if (!previous || previous.x !== point.x || previous.y !== point.y) points.push(point);
    });
  });
  return points;
}

export function orthogonalPath(sections: LayoutSection[] | undefined) {
  return orthogonalPoints(sections)?.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ") ?? null;
}

export const ELK_OPTIONS = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.edgeRouting": "ORTHOGONAL",
  "elk.spacing.nodeNode": "80",
  "elk.spacing.edgeNode": "16",
  "elk.layered.spacing.nodeNodeBetweenLayers": "78",
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
  "elk.layered.mergeEdges": "true",
  "elk.layered.nodePlacement.favorStraightEdges": "true",
  "elk.layered.unnecessaryBendpoints": "true",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
} as const;
