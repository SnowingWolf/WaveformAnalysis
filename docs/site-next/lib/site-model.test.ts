import { describe, expect, it } from "vitest";
import rawModel from "../fixture/site-model.v1.json";
import { parseSiteModel, SiteModelValidationError } from "./site-model";

describe("site-model/v1", () => {
  it("accepts the fixture and preserves the records contract", () => {
    const model = parseSiteModel(rawModel);
    const records = model.plugins.find((plugin) => plugin.provides === "records");

    expect(model.schema).toBe("site-model/v1");
    expect(records?.version).toBe("0.14.2");
    expect(records?.dependsOn[0]).toBe("raw_files");
    expect(records?.route).toBe("/plugins/records/");
    expect(model.routes.some((route) => route.path === "/plugins/records/" && route.kind === "plugin")).toBe(true);
    expect(model.contexts.some((page) => page.slug === "context")).toBe(true);
    expect(model.routes.every((route) => !route.path.endsWith(".html"))).toBe(true);
  });

  it("rejects a model with a stale schema", () => {
    expect(() => parseSiteModel({ ...rawModel, schema: "site-model/v0" })).toThrow(SiteModelValidationError);
  });

  it("rejects lineage edges that do not connect declared ports", () => {
    const invalid = structuredClone(rawModel) as { lineage: { edges: Array<Record<string, unknown>> } };
    invalid.lineage.edges[0] = { ...invalid.lineage.edges[0], sourcePort: "missing" };
    expect(() => parseSiteModel(invalid)).toThrow(/output to input/);
  });
});
