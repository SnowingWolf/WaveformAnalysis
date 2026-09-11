import type { NavigationGroup, SiteModel } from "./site-model";

export const SEARCH_INDEX_SCHEMA = "search-index/v1" as const;
export const SEARCH_INDEX_HREF = "/search-index.v1.json";

/** Version the stable static URL with the server-computed content digest. */
export function searchIndexHref(fingerprint: string): string {
  return `${SEARCH_INDEX_HREF}?fingerprint=${encodeURIComponent(fingerprint)}`;
}

export type SearchEntry = {
  title: string;
  summary: string;
  kind: string;
  url: string;
  keywords: string;
  /** The source section id when this result points at a section anchor. */
  anchor?: string;
};

export type SearchIndexPayload = {
  schema: typeof SEARCH_INDEX_SCHEMA;
  modelVersion: string;
  entries: SearchEntry[];
};

export type SearchIndex = SearchIndexPayload & {
  fingerprint: string;
};

export type SearchIndexRef = {
  href: string;
  expectedFingerprint: string;
};

/** The only model data serialized through the shared client shell. */
export type SiteShellModel = {
  project: { version: string };
  modelVersion: string;
  navigation: NavigationGroup[];
  searchIndex: SearchIndexRef;
};

function uniqueSearchTokens(values: string[]): string {
  const tokens = values.flatMap((value) => value.match(/[\p{L}\p{N}_:.()/'"+=-]+/gu) ?? []);
  return [...new Set(tokens.filter(Boolean))].sort().join(" ");
}

function collectStrings(value: unknown, output: string[], visited: Set<object>): void {
  if (typeof value === "string") {
    output.push(value);
    return;
  }
  if (typeof value !== "object" || value === null || visited.has(value)) return;
  visited.add(value);
  if (Array.isArray(value)) {
    value.forEach((item) => collectStrings(item, output, visited));
    return;
  }
  Object.values(value).forEach((item) => collectStrings(item, output, visited));
}

/** Extract searchable text without assuming a particular future block shape. */
function searchableText(value: unknown): string {
  const values: string[] = [];
  collectStrings(value, values, new Set<object>());
  return uniqueSearchTokens(values);
}

type SearchSection = { id: string; title: string };

function referenceKeywords(sections: SearchSection[]): string {
  return uniqueSearchTokens(sections.flatMap((section) => [
    section.id,
    section.title,
    searchableText(section),
  ]));
}

function guideKeywords(sections: SearchSection[]): string {
  return uniqueSearchTokens(sections.flatMap((section) => [
    section.id,
    section.title,
    searchableText(section),
  ]));
}

type SearchPage = {
  title: string;
  summary: string;
  kind: string;
  url: string;
  keywords: string;
  sections?: SearchSection[];
};

function pageEntries(page: SearchPage): SearchEntry[] {
  const base: SearchEntry = {
    title: page.title,
    summary: page.summary,
    kind: page.kind,
    url: page.url,
    keywords: page.keywords,
  };
  const sections = page.sections ?? [];
  return [
    base,
    ...sections.map((section) => ({
      title: `${page.title} · ${section.title}`,
      summary: page.summary,
      kind: page.kind,
      url: `${page.url}#${section.id}`,
      anchor: section.id,
      keywords: uniqueSearchTokens([
        page.title,
        page.summary,
        section.id,
        section.title,
      ]),
    })),
  ];
}

/** Derive the canonical full-text index from the complete versioned model. */
export function searchEntries(model: SiteModel): SearchEntry[] {
  const lineageLabels = model.lineage.nodes.map((node) => node.label).filter(Boolean);
  const lineageSummary = lineageLabels.length >= 2
    ? `查看 ${lineageLabels[0]} 到 ${lineageLabels[lineageLabels.length - 1]} 的插件处理链。`
    : "查看插件处理链。";
  const entries: SearchEntry[] = [
    {
      title: "WaveformAnalysis 文档",
      summary: model.project.tagline,
      kind: "首页",
      url: "/",
      keywords: searchableText({
        project: model.project,
        route: "/",
      }),
    },
    {
      title: "处理链概览",
      summary: lineageSummary,
      kind: "处理链",
      url: "/lineage/",
      keywords: searchableText(model.lineage),
    },
  ];

  model.plugins.forEach((plugin) => {
    entries.push(...pageEntries({
      title: plugin.provides,
      summary: plugin.summary,
      kind: "插件",
      url: plugin.route,
      keywords: uniqueSearchTokens([
        plugin.provides,
        plugin.category,
        plugin.outputKind,
        plugin.pluginClass ?? "",
        plugin.version ?? "",
        plugin.dependsOn.join(" "),
        plugin.usage,
        referenceKeywords(plugin.sections),
        searchableText(plugin.config),
        searchableText(plugin.fields),
      ]),
      sections: plugin.sections,
    }));
  });

  model.contexts.forEach((page) => {
    entries.push(...pageEntries({
      title: page.name,
      summary: page.summary,
      kind: "Context",
      url: page.route,
      keywords: uniqueSearchTokens([
        page.slug,
        "Context",
        page.profiles.join(" "),
        page.examples.join(" "),
        referenceKeywords(page.sections),
      ]),
      sections: page.sections,
    }));
  });

  model.accessors.forEach((page) => {
    entries.push(...pageEntries({
      title: page.name,
      summary: page.summary,
      kind: "Accessor",
      url: page.route,
      keywords: uniqueSearchTokens([
        page.slug,
        "Accessor",
        page.inputs.join(" "),
        page.methods.join(" "),
        page.selection.entry,
        page.selection.question,
        page.selection.scenario,
        referenceKeywords(page.sections),
      ]),
      sections: page.sections,
    }));
  });

  model.visualizations.forEach((page) => {
    entries.push(...pageEntries({
      title: page.name,
      summary: page.summary,
      kind: "可视化",
      url: page.route,
      keywords: uniqueSearchTokens([
        page.slug,
        "visualization",
        page.outputs.join(" "),
        referenceKeywords(page.sections),
      ]),
      sections: page.sections,
    }));
  });

  model.guides.forEach((page) => {
    entries.push(...pageEntries({
      title: page.title,
      summary: page.summary,
      kind: page.section,
      url: page.route,
      keywords: uniqueSearchTokens([
        page.slug,
        page.section,
        page.title,
        page.summary,
        guideKeywords(page.sections),
      ]),
      sections: page.sections,
    }));
  });

  // Source indexes are first-class model facts in the recovered content
  // contract. Include their section anchors when the producer supplies them;
  // older fixture models simply omit this optional collection.
  for (const page of model.source_indexes ?? []) {
    entries.push(...pageEntries({
      title: page.title,
      summary: page.summary,
      kind: "索引",
      url: page.route,
      keywords: searchableText(page),
      sections: page.sections,
    }));
  }

  // Keep route coverage complete if a future model adds a route that is not
  // represented by one of the typed collections yet.
  const knownRoutes = new Set(entries.map((entry) => entry.url.split("#", 1)[0]));
  model.routes.forEach((route) => {
    if (knownRoutes.has(route.path)) return;
    entries.push({
      title: route.title,
      summary: route.title,
      kind: route.kind,
      url: route.path,
      keywords: uniqueSearchTokens([route.path, route.title, route.kind]),
    });
    knownRoutes.add(route.path);
  });
  return entries;
}

/** Convert navigation into a useful, intentionally small error-state index. */
export function navigationSearchEntries(navigation: NavigationGroup[]): SearchEntry[] {
  const entriesFor = (
    items: NavigationGroup["items"],
    sectionTitle: string,
    ancestors: string[] = [],
  ): SearchEntry[] => items.flatMap((item) => {
    const labels = [...ancestors, item.label];
    return [
      {
        title: item.label,
        summary: [sectionTitle, ...ancestors].join(" · "),
        kind: sectionTitle,
        url: item.href,
        keywords: uniqueSearchTokens([sectionTitle, ...labels, item.href]),
      },
      ...entriesFor(item.children ?? [], sectionTitle, labels),
    ];
  });
  return navigation.flatMap((section) => entriesFor(section.items, section.title));
}

/** Rank matching entries before applying the dialog result limit. */
export function searchResults(entries: SearchEntry[], query: string, limit = 12): SearchEntry[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return entries.slice(0, limit);
  return entries
    .map((entry) => {
      const title = entry.title.toLocaleLowerCase();
      const summary = entry.summary.toLocaleLowerCase();
      const keywords = entry.keywords.toLocaleLowerCase();
      const keywordIndex = keywords.indexOf(normalized);
      if (!title.includes(normalized) && !summary.includes(normalized) && keywordIndex < 0) return null;
      let score = 0;
      // Keep the page destination visible when section anchors add many more
      // precise matches. Section titles still outrank this base-entry bonus.
      if (entry.anchor === undefined) score += 1_500;
      if (title === normalized) score += 10_000;
      else if (title.startsWith(normalized)) score += 5_000;
      else if (title.includes(normalized)) score += 2_000;
      if (summary.includes(normalized)) score += 1_200;
      if (keywordIndex >= 0) score += 1_100 - Math.min(keywordIndex, 1_000);
      return { entry, score };
    })
    .filter((result): result is { entry: SearchEntry; score: number } => result !== null)
    .sort((left, right) => right.score - left.score || left.entry.title.localeCompare(right.entry.title))
    .slice(0, limit)
    .map((result) => result.entry);
}

function rotateRight(value: number, bits: number): number {
  return (value >>> bits) | (value << (32 - bits));
}

/** Small browser-safe SHA-256 implementation for validating the lazy index. */
function sha256Hex(value: string): string {
  const bytes = new TextEncoder().encode(value);
  const paddedLength = bytes.length + 1 + ((64 - ((bytes.length + 1) % 64)) % 64);
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const bitLength = bytes.length * 8;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x1_0000_0000));
  view.setUint32(paddedLength - 4, bitLength >>> 0);

  const constants = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];
  let hash = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  const words = new Uint32Array(64);
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      words[index] = view.getUint32(offset + index * 4);
    }
    for (let index = 16; index < 64; index += 1) {
      const first = words[index - 15];
      const second = words[index - 2];
      const smallSigma0 = rotateRight(first, 7) ^ rotateRight(first, 18) ^ (first >>> 3);
      const smallSigma1 = rotateRight(second, 17) ^ rotateRight(second, 19) ^ (second >>> 10);
      words[index] = (words[index - 16] + smallSigma0 + words[index - 7] + smallSigma1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const bigSigma1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temp1 = (h + bigSigma1 + choice + constants[index] + words[index]) >>> 0;
      const bigSigma0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (bigSigma0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }
    hash = hash.map((value, index) => (value + [a, b, c, d, e, f, g, h][index]) >>> 0);
  }
  return hash.map((value) => value.toString(16).padStart(8, "0")).join("");
}

function canonicalSearchIndex(input: SearchIndexPayload): string {
  return JSON.stringify({
    schema: input.schema,
    modelVersion: input.modelVersion,
    entries: input.entries.map((entry) => ({
      title: entry.title,
      summary: entry.summary,
      kind: entry.kind,
      url: entry.url,
      keywords: entry.keywords,
      anchor: entry.anchor ?? null,
    })),
  });
}

export function searchIndexFingerprint(input: SearchIndexPayload): string {
  return sha256Hex(canonicalSearchIndex(input));
}

const fullSearchIndexCache = new WeakMap<SiteModel, SearchIndex>();

export function buildSearchIndex(model: SiteModel): SearchIndex {
  const cached = fullSearchIndexCache.get(model);
  if (cached) return cached;
  const payload: SearchIndexPayload = {
    schema: SEARCH_INDEX_SCHEMA,
    modelVersion: model.modelVersion,
    entries: searchEntries(model),
  };
  const index = { ...payload, fingerprint: searchIndexFingerprint(payload) };
  fullSearchIndexCache.set(model, index);
  return index;
}

/** Keep client shell props small: never serialize guide bodies or plugin schemas. */
export function siteShellModel(model: SiteModel): SiteShellModel {
  const index = buildSearchIndex(model);
  return {
    project: { version: model.project.version },
    modelVersion: model.modelVersion,
    navigation: model.navigation,
    searchIndex: {
      href: searchIndexHref(index.fingerprint),
      expectedFingerprint: index.fingerprint,
    },
  };
}
