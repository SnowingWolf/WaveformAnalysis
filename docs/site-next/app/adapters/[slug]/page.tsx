import { notFound } from "next/navigation";
import { CallableReferencePage } from "@/components/DocPage";
import { loadSiteModel, pageBySlug } from "@/lib/model";

export const dynamicParams = false;

export function generateStaticParams() {
  return loadSiteModel().contexts
    .filter((page) => page.route.startsWith("/adapters/"))
    .map((page) => ({ slug: page.slug }));
}

export default async function AdapterPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const siteModel = loadSiteModel();
  const adapters = siteModel.contexts.filter((page) => page.route.startsWith("/adapters/"));
  const page = pageBySlug(adapters, slug);
  if (!page) return notFound();
  return <CallableReferencePage model={siteModel} page={page} kind="Context" />;
}
