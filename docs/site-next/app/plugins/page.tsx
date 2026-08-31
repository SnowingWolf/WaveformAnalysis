import { SectionHeading } from "@/components/DocPage";
import { SiteShell } from "@/components/ServerSiteShell";
import { PluginDirectory } from "@/components/PluginDirectory";
import { loadSiteModel } from "@/lib/model";

export default function PluginsPage() {
  const siteModel = loadSiteModel();
  return <SiteShell model={siteModel} title="插件目录" toc={[{ id: "overview", label: "插件目录" }, { id: "directory", label: "内置插件" }, { id: "contract", label: "插件契约" }]}>
    <article className="doc-article"><div className="breadcrumbs"><span aria-current="page">插件</span></div><header className="page-intro"><h1>插件目录</h1><p className="page-intro__subtitle">按 provides、输出类型与处理阶段浏览内置插件。</p></header>
      <section id="overview" className="doc-section"><SectionHeading id="overview">插件目录</SectionHeading><p>插件通过 provides、depends_on 和输出 dtype 加入处理链。选择一个插件查看配置、字段与上游关系。</p></section>
      <section id="directory" className="doc-section"><SectionHeading id="directory">内置插件</SectionHeading><PluginDirectory plugins={siteModel.plugins} /></section>
      <section id="contract" className="doc-section"><SectionHeading id="contract">插件契约</SectionHeading><div className="contract-grid"><div><span className="contract-number">01</span><strong>provides</strong><p>每个插件提供一个稳定的数据产物名称。</p></div><div><span className="contract-number">02</span><strong>depends_on</strong><p>依赖关系决定 DAG 中的输入端口与执行顺序。</p></div><div><span className="contract-number">03</span><strong>output dtype</strong><p>输出字段和类型是可审计的消费契约。</p></div></div></section>
    </article>
  </SiteShell>;
}
