import type { NavigationGroup, SiteModel } from "./site-model";

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

/** Derive the search index from the versioned collections and route registry. */
export function searchEntries(model: SiteModel): SearchEntry[] {
  const pluginEntries = model.plugins.map((plugin) => ({
    title: plugin.provides,
    summary: plugin.summary,
    kind: "插件",
    url: plugin.route,
    keywords: `${plugin.provides} ${plugin.category} ${plugin.outputKind}`,
  }));
  const pageEntries = [
    ...model.contexts.map((page) => ({ title: page.name, summary: page.summary, kind: "Context", url: page.route, keywords: `${page.slug} Context` })),
    ...model.accessors.map((page) => ({ title: page.name, summary: page.summary, kind: "Accessor", url: page.route, keywords: `${page.slug} Accessor` })),
    ...model.visualizations.map((page) => ({ title: page.name, summary: page.summary, kind: "可视化", url: page.route, keywords: `${page.slug} visualization` })),
    ...model.guides.map((page) => ({ title: page.title, summary: page.summary, kind: page.section, url: page.route, keywords: `${page.title} ${page.summary}` })),
  ];
  return [
    { title: "WaveformAnalysis 文档", summary: model.project.tagline, kind: "首页", url: "/", keywords: "WaveformAnalysis 文档" },
    { title: "处理链概览", summary: "查看 raw_files 到 events 的插件处理 DAG。", kind: "处理链", url: "/lineage/", keywords: "DAG lineage 处理链 raw_files records" },
    ...pluginEntries,
    ...pageEntries,
  ];
}

/** Keep client shell props small: never serialize guide bodies or plugin schemas on every page. */
export function siteShellModel(model: SiteModel): SiteShellModel {
  return {
    project: { version: model.project.version },
    navigation: model.navigation,
    search: searchEntries(model),
  };
}
