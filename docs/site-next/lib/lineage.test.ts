import { describe, expect, it } from "vitest";
import rawModel from "../fixture/site-model.v1.json";
import { dtypeSummary, visibleGraph, edgeHandleMapping, orthogonalPath } from "./lineage";
import { parseSiteModel } from "./site-model";

describe("lineage helpers", () => {
  const model = parseSiteModel(rawModel).lineage;

  it("uses the live edges to build a focused neighborhood", () => {
    const graph = visibleGraph(model, "full", "records");
    const ids = graph.nodes.map((node) => node.id);
    expect(ids).toContain("raw_files");
    expect(ids).toContain("records");
    expect(ids).toContain("basic_features");
    expect(graph.edges.some((edge) => edge.source === "raw_files" && edge.target === "records")).toBe(true);
  });

  it("keeps Overview and Full tied to their declared view sets", () => {
    const overview = visibleGraph(model, "overview");
    const full = visibleGraph(model, "full");
    const focused = visibleGraph(model, "full", "records");

    expect(overview.nodes).toHaveLength(model.views.overview.length);
    expect(full.nodes).toHaveLength(model.views.full.length);
    expect(full.nodes.length).toBeGreaterThan(focused.nodes.length);
    expect(full.nodes.map((node) => node.id)).toEqual(model.views.full);
  });

  it("maps declared port ids for React Flow and normalizes orthogonal points", () => {
    const edge = model.edges.find((item) => item.source === "raw_files" && item.target === "records");
    expect(edge).toBeDefined();
    expect(edgeHandleMapping(edge!)).toEqual({
      source: "raw_files",
      sourceHandle: edge!.sourcePort,
      target: "records",
      targetHandle: edge!.targetPort,
    });
    expect(orthogonalPath([{ startPoint: { x: 0, y: 0 }, bendPoints: [{ x: 20, y: 0 }, { x: 20, y: 10 }], endPoint: { x: 40, y: 10 } }])).toBe("M 0 0 L 20 0 L 20 10 L 40 10");
  });

  it("summarizes long structured dtypes without changing short scalar dtypes", () => {
    expect(dtypeSummary("float32")).toBe("float32");
    expect(dtypeSummary("[('peak_id', '<i8'), ('area', '<f4'), ('height', '<f4')]")).toBe("3 fields");
    expect(dtypeSummary("a custom dtype representation that is too long")).toBe("structured dtype");
  });
});
