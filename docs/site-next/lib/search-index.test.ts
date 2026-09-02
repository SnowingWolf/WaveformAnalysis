import { describe, expect, it } from "vitest";
import rawModel from "../fixture/site-model.v1.json";
import {
  buildSearchIndex,
  navigationSearchEntries,
  searchIndexFingerprint,
  searchResults,
  siteShellModel,
  type SearchIndexPayload,
} from "./search";
import { parseSiteModel, type SiteModel } from "./site-model";
import {
  clearSearchIndexCache,
  loadSearchIndex,
  SearchIndexValidationError,
  validateSearchIndex,
} from "./search-index";

function payload(): SearchIndexPayload {
  return {
    schema: "search-index/v1",
    modelVersion: "fixture-1",
    entries: [
      {
        title: "RecordsView · 波形访问",
        summary: "按 record_id 读取波形。",
        kind: "Accessor",
        url: "/accessors/records-view/#wave-access",
        anchor: "wave-access",
        keywords: "records record_id wave_access",
      },
    ],
  };
}

function documentFor(value: SearchIndexPayload = payload()) {
  return { ...value, fingerprint: searchIndexFingerprint(value) };
}

function responseFor(value: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 503, json: async () => value } as Response;
}

describe("search-index/v1", () => {
  it("uses SHA-256 over the canonical payload", () => {
    expect(documentFor().fingerprint).toBe(
      "e7f2b09ed1731fa37949f3afd5cc545486b9aa044b57df6fcd78bd2e0e1ac18e",
    );
  });

  it("emits every real reference section as a canonical anchor result", () => {
    const index = buildSearchIndex(rawModel as unknown as SiteModel);
    const records = rawModel.accessors.find((page) => page.slug === "records-view");

    expect(records).toBeDefined();
    for (const section of records?.sections ?? []) {
      expect(index.entries).toContainEqual(expect.objectContaining({
        anchor: section.id,
        url: `${records?.route}#${section.id}`,
      }));
    }
    expect(index.entries.some((entry) => entry.url === "/plugins/records/#overview")).toBe(true);
    const sourceIndex = rawModel.source_indexes?.[0];
    const sourceSection = sourceIndex?.sections[0];
    if (sourceIndex && sourceSection) {
      expect(index.entries).toContainEqual(expect.objectContaining({
        anchor: sourceSection.id,
        url: `${sourceIndex.route}#${sourceSection.id}`,
      }));
    }
  });

  it("versions the shell index URL with its content fingerprint", () => {
    const model = parseSiteModel(rawModel);
    const shell = siteShellModel(model);

    expect(shell.searchIndex.href).toBe(
      `/search-index.v1.json?fingerprint=${shell.searchIndex.expectedFingerprint}`,
    );
  });

  it("loads one URL once and reuses the module promise", async () => {
    clearSearchIndexCache();
    const value = documentFor();
    let calls = 0;
    const fetcher = async () => {
      calls += 1;
      return responseFor(value);
    };

    const first = loadSearchIndex("/search-index.v1.json", {
      expectedFingerprint: value.fingerprint,
      expectedModelVersion: value.modelVersion,
      fetcher,
    });
    const second = loadSearchIndex("/search-index.v1.json", {
      expectedFingerprint: value.fingerprint,
      expectedModelVersion: value.modelVersion,
      fetcher,
    });

    expect(second).toBe(first);
    await expect(first).resolves.toEqual(value);
    expect(calls).toBe(1);
    clearSearchIndexCache();
  });

  it("clears rejected requests so a failed load can be retried", async () => {
    clearSearchIndexCache();
    const value = documentFor();
    let calls = 0;
    const fetcher = async () => {
      calls += 1;
      return responseFor(calls === 1 ? { ...value, fingerprint: "0".repeat(64) } : value);
    };

    await expect(loadSearchIndex("/retry.json", {
      expectedFingerprint: value.fingerprint,
      fetcher,
    })).rejects.toThrow(SearchIndexValidationError);
    await expect(loadSearchIndex("/retry.json", {
      expectedFingerprint: value.fingerprint,
      fetcher,
    })).resolves.toEqual(value);
    expect(calls).toBe(2);
    clearSearchIndexCache();
  });

  it("rejects a validly shaped index with the wrong expected fingerprint", () => {
    const value = documentFor();
    expect(() => validateSearchIndex(value, { expectedFingerprint: "f".repeat(64) }))
      .toThrow(/fingerprint mismatch/);
  });

  it("provides navigation results when the full index is unavailable", () => {
    const navigation = [{
      id: "reference",
      title: "参考",
      items: [{
        label: "命令行工具",
        href: "/cli/",
        icon: "guide",
        children: [{ label: "waveform-docs", href: "/cli/WAVEFORM_DOCS/", icon: "file" }],
      }],
    }];
    const fallback = navigationSearchEntries(navigation);

    expect(searchResults(fallback, "waveform-docs")).toEqual([
      expect.objectContaining({
        url: "/cli/WAVEFORM_DOCS/",
        summary: "参考 · 命令行工具",
      }),
    ]);
  });
});
