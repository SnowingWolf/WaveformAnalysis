import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Breadcrumbs, GuideSections } from "@/components/DocPage";
import { SiteShell } from "@/components/ServerSiteShell";
import { allGuides, guideBySlug, loadSiteModel } from "@/lib/model";

export const dynamicParams = false;

export function generateStaticParams() {
  return allGuides(loadSiteModel()).map((guide) => ({ slug: guide.route.replace(/^\//, "").replace(/\/$/, "").split("/") }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string[] }> }): Promise<Metadata> {
  const { slug } = await params;
  const guide = guideBySlug(loadSiteModel(), slug);
  return guide ? { title: guide.title, description: guide.summary } : {};
}

export default async function GuidePage({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  const siteModel = loadSiteModel();
  const guide = guideBySlug(siteModel, slug);
  if (!guide) return notFound();
  const toc = guide.sections.map((section) => ({ id: section.id, label: section.title }));
  return <SiteShell model={siteModel} title={guide.title} toc={toc}>
    <article className="doc-article"><Breadcrumbs items={[{ label: guide.section }, { label: guide.title }]} /><header className="page-intro"><h1>{guide.title}</h1><p className="page-intro__subtitle">{guide.summary}</p></header>
      <GuideSections sections={guide.sections} />
    </article>
  </SiteShell>;
}
