import { SectionHeading } from "@/components/DocPage";
import { ReferenceDirectory } from "@/components/ReferenceDirectory";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export default function ContextsPage() {
  const siteModel = loadSiteModel();
  const contexts = siteModel.contexts.filter((page) => page.route.startsWith("/contexts/"));
  return <SiteShell model={siteModel} title="Context" toc={[{ id: "overview", label: "Context 与适配器" }, { id: "directory", label: "参考页面" }]}>
    <article className="doc-article">
      <div className="breadcrumbs"><span aria-current="page">Context</span></div>
      <header className="page-intro"><h1>Context 与适配器</h1><p className="page-intro__subtitle">协调配置、插件依赖、lineage 与缓存，统一 DAQ 输入边界。</p></header>
      <section id="overview" className="doc-section"><SectionHeading id="overview">Context 与适配器</SectionHeading><p>Context 是分析运行时的协调层；DAQ 适配器负责格式、目录布局与时间语义。所有数据访问显式传入 run_id。</p></section>
      <section id="directory" className="doc-section"><SectionHeading id="directory">参考页面</SectionHeading><ReferenceDirectory items={contexts} label="Context" /></section>
    </article>
  </SiteShell>;
}
