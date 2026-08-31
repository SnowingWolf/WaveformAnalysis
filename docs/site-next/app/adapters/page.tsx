import { SectionHeading } from "@/components/DocPage";
import { ReferenceDirectory } from "@/components/ReferenceDirectory";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export default function AdaptersPage() {
  const siteModel = loadSiteModel();
  const adapters = siteModel.contexts.filter((page) => page.route.startsWith("/adapters/"));
  return <SiteShell model={siteModel} title="DAQ 适配器" toc={[{ id: "overview", label: "DAQ 适配器" }, { id: "directory", label: "参考页面" }]}>
    <article className="doc-article"><div className="breadcrumbs"><span aria-current="page">DAQ 适配器</span></div><header className="page-intro"><h1>DAQ 适配器</h1><p className="page-intro__subtitle">隔离采集格式、目录布局与时间语义。</p></header><section id="overview" className="doc-section"><SectionHeading id="overview">DAQ 适配器</SectionHeading><p>适配器把硬件格式转换为统一的文档与处理边界。</p></section><section id="directory" className="doc-section"><SectionHeading id="directory">参考页面</SectionHeading><ReferenceDirectory items={adapters} label="DAQ 适配器" /></section></article>
  </SiteShell>;
}
