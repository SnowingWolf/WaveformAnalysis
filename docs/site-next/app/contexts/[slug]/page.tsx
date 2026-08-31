import { notFound } from "next/navigation";
import { CallableReferencePage } from "@/components/DocPage";
import { loadSiteModel, pageBySlug } from "@/lib/model";

export const dynamicParams = false;

export function generateStaticParams() {
  return loadSiteModel().contexts
    .filter((page) => page.route.startsWith("/contexts/"))
    .map((page) => ({ slug: page.slug }));
}

export default async function ContextPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const siteModel = loadSiteModel();
  const page = pageBySlug(
    siteModel.contexts.filter((entry) => entry.route.startsWith("/contexts/")),
    slug,
  );
  if (!page) return notFound();
  return <CallableReferencePage model={siteModel} page={page} kind="Context" />;
}
