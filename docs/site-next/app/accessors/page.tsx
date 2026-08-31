import { SectionHeading } from "@/components/DocPage";
import { ReferenceDirectory } from "@/components/ReferenceDirectory";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export default function AccessorsPage() {
  const siteModel = loadSiteModel();
  return <SiteShell model={siteModel} title="Accessor" toc={[{ id: "overview", label: "Accessor 接口" }, { id: "directory", label: "参考页面" }]}><article className="doc-article"><div className="breadcrumbs"><span aria-current="page">Accessor</span></div><header className="page-intro"><h1>Accessor 接口</h1><p className="page-intro__subtitle">从稳定数据产物中进行可审计的查询、筛选与波形访问。</p></header><section id="overview" className="doc-section"><SectionHeading id="overview">Accessor 接口</SectionHeading><p>Accessor 负责面向分析问题的查询入口，不改变底层插件和数据契约。</p></section><section id="directory" className="doc-section"><SectionHeading id="directory">参考页面</SectionHeading><ReferenceDirectory items={siteModel.accessors} label="Accessor" /></section></article></SiteShell>;
}
