import { describe, expect, it } from "vitest";
import rawModel from "../fixture/site-model.v1.json";
import { dtypeSummary, visibleGraph, edgeHandleMapping, orthogonalPath } from "./lineage";
import { parseSiteModel } from "./site-model";

describe("lineage helpers", () => {
  const model = parseSiteModel(rawModel).lineage;

  it("uses the live edges to build a focused neighborhood", () => {
    const graph = visibleGraph(model, "full", "records");
    expect(graph.nodes.map((node) => node.id)).toEqual(["raw_files", "records", "wave_pool"]);
    expect(graph.edges.map((edge) => edge.id)).toEqual(["raw_files-records", "records-wave_pool"]);
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
    expect(edgeHandleMapping(model.edges[0])).toEqual({
      source: "raw_files",
      sourceHandle: "raw_files.out",
      target: "records",
      targetHandle: "records.in",
    });
    expect(orthogonalPath([{ startPoint: { x: 0, y: 0 }, bendPoints: [{ x: 20, y: 0 }, { x: 20, y: 10 }], endPoint: { x: 40, y: 10 } }])).toBe("M 0 0 L 20 0 L 20 10 L 40 10");
  });

  it("summarizes long structured dtypes without changing short scalar dtypes", () => {
    expect(dtypeSummary("float32")).toBe("float32");
    expect(dtypeSummary("[('peak_id', '<i8'), ('area', '<f4'), ('height', '<f4')]")).toBe("3 fields");
    expect(dtypeSummary("a custom dtype representation that is too long")).toBe("structured dtype");
  });
});
