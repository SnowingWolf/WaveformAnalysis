import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import fixtureModel from "@/fixture/site-model.v1.json";
import {
  parseSiteModel,
  type AccessorModel,
  type ContextModel,
  type GuideModel,
  type PluginModel,
  type SiteModel,
  type VisualizationModel,
} from "./site-model";

const SITE_MODEL_ENV_NAMES = [
  "WAVEFORM_DOCS_SITE_MODEL",
  "WAVEFORM_SITE_MODEL_PATH",
  "WAVEFORM_DOCS_MODEL_PATH",
] as const;

/** Load generated site facts at build time; use the fixture only without an env path. */
export function loadSiteModel(): SiteModel {
  const configuredPath = SITE_MODEL_ENV_NAMES.map((name) => process.env[name]).find(Boolean);
  if (!configuredPath) return parseSiteModel(fixtureModel);

  const absolutePath = resolve(configuredPath);
  let payload: unknown;
  try {
    payload = JSON.parse(readFileSync(absolutePath, "utf8")) as unknown;
  } catch (error) {
    throw new Error(`Unable to read site model at ${absolutePath}`, { cause: error });
  }
  return parseSiteModel(payload);
}

export type ReferenceModel = ContextModel | AccessorModel | VisualizationModel;

export function pluginByProvides(model: SiteModel, provides: string): PluginModel | undefined {
  return model.plugins.find((plugin) => plugin.provides === provides);
}

export function pageBySlug<T extends ReferenceModel>(collection: T[], slug: string): T | undefined {
  return collection.find((page) => page.slug === slug);
}

export function guideBySlug(model: SiteModel, slugParts: string[]): GuideModel | undefined {
  const route = `/${slugParts.join("/")}/`;
  return model.guides.find((guide) => guide.route === route);
}

export function allGuides(model: SiteModel): GuideModel[] {
  return model.guides;
}

export function routeLabel(model: SiteModel, pathname: string) {
  if (pathname === "/") return "快速开始";
  const entry = model.navigation.flatMap((section) => section.items).find((item) => item.href === pathname);
  if (entry) return entry.label;
  const route = model.routes.find((candidate) => candidate.path === pathname);
  if (!route) return "文档";
  const plugin = model.plugins.find((entry) => entry.route === route.path);
  if (plugin) return plugin.provides;
  const page = [...model.contexts, ...model.accessors, ...model.visualizations].find((entry) => entry.route === route.path);
  if (page) return page.name;
  const guide = allGuides(model).find((entry) => entry.route === route.path);
  return guide?.title ?? route.title;
}
