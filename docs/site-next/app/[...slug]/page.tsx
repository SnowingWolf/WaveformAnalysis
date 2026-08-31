import { notFound } from "next/navigation";
import { Breadcrumbs, CodeBlock, DataTable, SectionHeading } from "@/components/DocPage";
import { SiteShell } from "@/components/ServerSiteShell";
import { allGuides, guideBySlug, loadSiteModel } from "@/lib/model";

export const dynamicParams = false;

export function generateStaticParams() {
  return allGuides(loadSiteModel()).map((guide) => ({ slug: guide.route.replace(/^\//, "").replace(/\/$/, "").split("/") }));
}

export default async function GuidePage({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  const siteModel = loadSiteModel();
  const guide = guideBySlug(siteModel, slug);
  if (!guide) return notFound();
  const toc = guide.sections.map((section) => ({ id: section.id, label: section.title }));
  return <SiteShell model={siteModel} title={guide.title} toc={toc}>
    <article className="doc-article"><Breadcrumbs items={[{ label: guide.section }, { label: guide.title }]} /><header className="page-intro"><h1>{guide.title}</h1><p className="page-intro__subtitle">{guide.summary}</p></header>
      {guide.sections.map((section) => <section className="doc-section" id={section.id} key={section.id}><SectionHeading id={section.id}>{section.title}</SectionHeading>{section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}{section.bullets && <ul className="doc-list">{section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>}{section.table && <DataTable headers={section.table.headers} rows={section.table.rows} />}{section.code && <CodeBlock code={section.code} />}</section>)}
    </article>
  </SiteShell>;
}
