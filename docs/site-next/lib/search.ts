import type { NavigationGroup, ReferenceSection, SiteModel } from "./site-model";

export type SearchEntry = {
  title: string;
  summary: string;
  kind: string;
  url: string;
  keywords: string;
};

export type SiteShellModel = {
  project: { version: string };
  navigation: NavigationGroup[];
  search: SearchEntry[];
};

function uniqueSearchTokens(values: string[]): string {
  const tokens = values.flatMap((value) => value.match(/[\p{L}\p{N}_:.()/'"+=-]+/gu) ?? []);
  return [...new Set(tokens.filter(Boolean))].join(" ");
}

function referenceKeywords(sections: ReferenceSection[]): string {
  return uniqueSearchTokens(sections.flatMap((section) => [
    section.id,
    section.title,
    ...section.blocks.flatMap((block) => [
      block.kind,
      block.text ?? "",
      block.title ?? "",
      block.code ?? "",
      block.mermaid ?? "",
      block.mathml ?? "",
      block.image_alt ?? "",
      block.image_caption ?? "",
      ...(block.items ?? []),
      ...(block.table_headers ?? []),
      ...(block.table_rows ?? []).flat(),
    ]),
  ]));
}

function guideKeywords(sections: SiteModel["guides"][number]["sections"]): string {
  return uniqueSearchTokens(sections.flatMap((section) => [
    section.id,
    section.title,
    ...section.paragraphs,
    ...(section.bullets ?? []),
    ...(section.table?.headers ?? []),
    ...(section.table?.rows ?? []).flat(),
    section.code ?? "",
  ]));
}

/** Derive the search index from the versioned collections and route registry. */
export function searchEntries(model: SiteModel): SearchEntry[] {
  const pluginEntries = model.plugins.map((plugin) => ({
    title: plugin.provides,
    summary: plugin.summary,
    kind: "插件",
    url: plugin.route,
    keywords: `${plugin.provides} ${plugin.category} ${plugin.outputKind} ${referenceKeywords(plugin.sections)}`,
  }));
  const pageEntries = [
    ...model.contexts.map((page) => ({ title: page.name, summary: page.summary, kind: "Context", url: page.route, keywords: `${page.slug} Context ${referenceKeywords(page.sections)}` })),
    ...model.accessors.map((page) => ({ title: page.name, summary: page.summary, kind: "Accessor", url: page.route, keywords: `${page.slug} Accessor ${page.selection.entry} ${page.selection.question} ${referenceKeywords(page.sections)}` })),
    ...model.visualizations.map((page) => ({ title: page.name, summary: page.summary, kind: "可视化", url: page.route, keywords: `${page.slug} visualization ${referenceKeywords(page.sections)}` })),
    ...model.guides.map((page) => ({ title: page.title, summary: page.summary, kind: page.section, url: page.route, keywords: `${page.title} ${page.summary} ${guideKeywords(page.sections)}` })),
  ];
  return [
    { title: "WaveformAnalysis 文档", summary: model.project.tagline, kind: "首页", url: "/", keywords: "WaveformAnalysis 文档" },
    { title: "处理链概览", summary: "查看 raw_files 到 events 的插件处理 DAG。", kind: "处理链", url: "/lineage/", keywords: "DAG lineage 处理链 raw_files records" },
    ...pluginEntries,
    ...pageEntries,
  ];
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

/** Keep client shell props small: never serialize guide bodies or plugin schemas on every page. */
export function siteShellModel(model: SiteModel): SiteShellModel {
  return {
    project: { version: model.project.version },
    navigation: model.navigation,
    search: searchEntries(model),
  };
}
