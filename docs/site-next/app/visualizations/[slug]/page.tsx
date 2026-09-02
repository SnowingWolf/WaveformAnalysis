import { notFound } from "next/navigation";
import { VisualizationReferencePage } from "@/components/DocPage";
import { loadSiteModel, pageBySlug } from "@/lib/model";

export const dynamicParams = false;

export function generateStaticParams() { return loadSiteModel().visualizations.map((page) => ({ slug: page.slug })); }

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const page = pageBySlug(loadSiteModel().visualizations, slug);
  return page ? { title: page.name, description: page.summary } : {};
}

export default async function VisualizationPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const siteModel = loadSiteModel();
  const page = pageBySlug(siteModel.visualizations, slug);
  if (!page) return notFound();
  return <VisualizationReferencePage model={siteModel} page={page} />;
}
import type { Metadata } from "next";
