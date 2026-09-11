import { describe, expect, it } from "vitest";
import rawModel from "../fixture/site-model.v1.json";
import { parseSiteModel, SiteModelValidationError } from "./site-model";
import { searchEntries, searchResults } from "./search";

describe("site-model/v1", () => {
  it("accepts the fixture and preserves the records contract", () => {
    const model = parseSiteModel(rawModel);
    const records = model.plugins.find((plugin) => plugin.provides === "records");

    expect(model.schema).toBe("site-model/v1");
    expect(records?.version).toBe("0.14.3");
    expect(records?.dependsOn[0]).toBe("raw_files");
    expect(records?.route).toBe("/plugins/records/");
    expect(model.routes.some((route) => route.path === "/plugins/records/" && route.kind === "plugin")).toBe(true);
    expect(model.contexts.some((page) => page.slug === "context")).toBe(true);
    expect(model.contexts.some((page) => page.slug === "records-view")).toBe(false);
    const recordsView = model.accessors.find((page) => page.slug === "records-view");
    expect(recordsView?.route).toBe("/accessors/records-view/");
    expect(recordsView?.pageKind).toBe("callable");
    expect(recordsView?.sections.map((section) => section.id)).toContain("wave-access");
    expect(recordsView?.methods).toContain("waves");
    const entries = searchEntries(model);
    const recordsSearch = entries.find((entry) => entry.url === "/accessors/records-view/");
    expect(recordsSearch?.kind).toBe("Accessor");
    for (const keyword of [
      "record_id",
      "wave_pool",
      "query_time_window",
      "sample_start",
      "sample_end",
      "pad_to",
      "baseline_correct",
    ]) {
      expect(recordsSearch?.keywords).toContain(keyword);
      expect(searchResults(entries, keyword).some((entry) => entry.url === "/accessors/records-view/")).toBe(true);
    }
    expect(entries.reduce((size, entry) => size + entry.keywords.length, 0)).toBeLessThan(500_000);
    expect(model.plugins.every((plugin) => plugin.sections.length === 4)).toBe(true);
    expect(model.routes.every((route) => !route.path.endsWith(".html"))).toBe(true);
  });

  it.each(["missing", "duplicate", "stale-version", "wrong-dependency"])(
    "rejects an invalid records contract: %s",
    (mutation) => {
      const model = structuredClone(rawModel) as unknown as {
        plugins: Array<{ provides: string; version: string | null; dependsOn: string[] }>;
      };
      const records = model.plugins.find((plugin) => plugin.provides === "records");

      if (mutation === "missing") {
        model.plugins = model.plugins.filter((plugin) => plugin.provides !== "records");
      } else if (!records) {
        throw new Error("fixture records plugin is missing");
      } else if (mutation === "duplicate") {
        model.plugins.push({ ...records, dependsOn: [...records.dependsOn] });
      } else if (mutation === "stale-version") {
        records.version = "0.14.2";
      } else {
        records.dependsOn = ["st_waveforms", "raw_files"];
      }

      expect(() => parseSiteModel(model)).toThrow(
        "records plugin must be v0.14.3 with raw_files as its first dependency",
      );
    },
  );

  it("preserves ordered guide blocks and source-index bodies", () => {
    const model = parseSiteModel(rawModel);
    const quickstart = model.guides.find((guide) => guide.route === "/user-guide/QUICKSTART_GUIDE/");
    expect(quickstart?.source).toBe("docs/user-guide/QUICKSTART_GUIDE.md");
    const blocks = quickstart?.sections.flatMap((section) => section.blocks) ?? [];
    expect(blocks.some((block) => block.kind === "list" && block.ordered === true)).toBe(true);
    expect(blocks.filter((block) => block.kind === "code").length).toBeGreaterThan(1);
    expect(blocks.some((block) => block.kind === "table")).toBe(true);
    expect(blocks.some((block) => block.inlines?.some((inline) => inline.kind === "link"))).toBe(true);

    const pluginIndex = model.source_indexes.find((index) => index.route === "/plugins/");
    expect(pluginIndex?.sections.length).toBeGreaterThan(0);
    expect(pluginIndex?.sections.flatMap((section) => section.blocks).some((block) =>
      block.inlines?.some((inline) => inline.kind === "link" && inline.href?.startsWith("/")),
    )).toBe(true);
  });

  it("rejects a model with a stale schema", () => {
    expect(() => parseSiteModel({ ...rawModel, schema: "site-model/v0" })).toThrow(SiteModelValidationError);
  });

  it("accepts optional navigation children and rejects malformed child collections", () => {
    const withChildren = structuredClone(rawModel) as unknown as {
      navigation: Array<{ items: Array<Record<string, unknown>> }>;
    };
    withChildren.navigation[1].items[7].children = [
      { label: "waveform-docs", href: "/cli/WAVEFORM_DOCS/", icon: "file" },
    ];
    const parsed = parseSiteModel(withChildren);
    expect(parsed.navigation[1].items[7].children?.[0].href).toBe("/cli/WAVEFORM_DOCS/");

    withChildren.navigation[1].items[7].children = { href: "/cli/WAVEFORM_DOCS/" };
    expect(() => parseSiteModel(withChildren)).toThrow(/children must be an array/);
  });

  it("rejects lineage edges that do not connect declared ports", () => {
    const invalid = structuredClone(rawModel) as { lineage: { edges: Array<Record<string, unknown>> } };
    invalid.lineage.edges[0] = { ...invalid.lineage.edges[0], sourcePort: "missing" };
    expect(() => parseSiteModel(invalid)).toThrow(/output to input/);
  });
});

it("preserves recursive list trees and rejects invalid nested starts", () => {
  const raw = structuredClone(rawModel) as unknown as { guides: { sections: { blocks: Record<string, unknown>[] }[] }[] };
  const tree = { ordered: true, start: 3, entries: [
    { text: "parent", children: [{ ordered: false, entries: [{ text: "child" }] }] },
  ] };
  raw.guides[0].sections[0].blocks = [{ kind: "list", list_tree: tree }];
  expect(parseSiteModel(raw).guides[0].sections[0].blocks[0].list_tree).toEqual(tree);
  Object.assign(tree.entries[0].children[0], { start: -1 });
  expect(() => parseSiteModel(raw)).toThrow(/children\[0\].start/);
});
