import { notFound } from "next/navigation";
import { PluginReferencePage } from "@/components/DocPage";
import { loadSiteModel, pluginByProvides } from "@/lib/model";

export const dynamicParams = false;

export function generateStaticParams() {
  return loadSiteModel().plugins.map((plugin) => ({ provides: plugin.provides }));
}

export async function generateMetadata({ params }: { params: Promise<{ provides: string }> }): Promise<Metadata> {
  const { provides } = await params;
  const plugin = pluginByProvides(loadSiteModel(), provides);
  return plugin ? { title: plugin.provides, description: `${plugin.summary} 版本 ${plugin.version ?? "未标注"}。` } : {};
}

export default async function PluginPage({ params }: { params: Promise<{ provides: string }> }) {
  const { provides } = await params;
  const siteModel = loadSiteModel();
  const plugin = pluginByProvides(siteModel, provides);
  if (!plugin) return notFound();
  return <PluginReferencePage model={siteModel} plugin={plugin} />;
}
import type { Metadata } from "next";
