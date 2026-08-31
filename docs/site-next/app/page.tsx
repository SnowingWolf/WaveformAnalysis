import { StaticLink as Link } from "@/components/StaticLink";
import { CodeBlock, SectionHeading } from "@/components/DocPage";
import { Icon } from "@/components/icons";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

function PipelineGlyph({ kind }: { kind: string }) {
  if (kind === "raw") return <svg viewBox="0 0 100 54" aria-hidden="true"><rect x="25" y="12" width="32" height="34" rx="2" /><rect x="33" y="8" width="32" height="34" rx="2" /><rect x="41" y="15" width="32" height="32" rx="2" /><circle cx="80" cy="27" r="2" /><circle cx="87" cy="27" r="2" /></svg>;
  if (kind === "event") return <svg viewBox="0 0 100 54" aria-hidden="true"><path d="M18 13H82M18 27H82M18 41H82" /><circle cx="30" cy="13" r="3" /><circle cx="68" cy="13" r="3" /><circle cx="44" cy="27" r="3" /><circle cx="74" cy="27" r="3" /><circle cx="25" cy="41" r="3" /><circle cx="59" cy="41" r="3" /></svg>;
  if (kind === "peak") return <svg viewBox="0 0 100 54" aria-hidden="true"><path className="pipeline-baseline" d="M10 43H90" /><path d="M10 43H28L35 40L43 10L51 43H64L70 38L76 20L82 43H90" /></svg>;
  return <svg viewBox="0 0 100 54" aria-hidden="true"><path className="pipeline-baseline" d="M8 32H92" /><path d="M8 33L14 29L20 36L27 18L34 42L42 12L49 35L56 25L63 39L71 16L78 31L86 22L92 30" /></svg>;
}

export default function HomePage() {
  const siteModel = loadSiteModel();
  const chain = ["raw_files", "records", "hit_threshold", "peaklets", "peaks", "events"].reduce<Array<[string, string, string, string]>>((items, id) => {
    const node = siteModel.lineage.nodes.find((entry) => entry.id === id);
    const plugin = siteModel.plugins.find((entry) => entry.provides === id);
    if (node && plugin) items.push([plugin.provides, node.summary, node.kind, plugin.route]);
    return items;
  }, []);
  const workflows = siteModel.guides.map((page) => [page.title, page.summary, page.route] as const).slice(0, 5);

  return <SiteShell model={siteModel} title="快速开始" toc={[{ id: "pipeline", label: "处理链概览" }, { id: "workflows", label: "按工作流查找" }, { id: "minimum-example", label: "运行最小示例" }, { id: "concepts", label: "相关概念" }]}>
    <article className="doc-article home-article">
      <header className="home-hero"><h1>WaveformAnalysis 文档</h1><p>从 DAQ 波形到事件构建，理解处理链、数据产物与分析接口。</p><div className="hero-actions"><Link className="button button--primary" href="/user-guide/EXAMPLES_GUIDE/">快速开始 <Icon name="arrow" size={17} /></Link><Link className="button button--secondary" href="/lineage/">查看处理链 <Icon name="arrow" size={17} /></Link></div></header>
      <section id="pipeline" className="doc-section pipeline-section"><SectionHeading id="pipeline">处理链概览</SectionHeading><p className="section-lede">WaveformAnalysis 采用插件驱动的 DAG 处理链，将原始 DAQ 波形转化为物理事件与分析结果。</p><div className="pipeline-diagram" aria-label="raw_files 到 events 的处理链">{chain.map(([name, label, kind, href], index) => <div className="pipeline-step" key={name}><Link href={href} className={`pipeline-card pipeline-card--${kind}`}><strong>{name}</strong><span className="pipeline-graphic"><PipelineGlyph kind={kind} /></span><small>{label}</small></Link>{index < chain.length - 1 && <Icon name="arrow" size={27} className="pipeline-arrow" />}</div>)}</div></section>
      <section id="workflows" className="doc-section"><SectionHeading id="workflows">按工作流查找</SectionHeading><div className="workflow-table"><div className="workflow-table__head"><span>工作流</span><span>描述</span><span>入口</span></div>{workflows.map(([name, description, href]) => <div className="workflow-table__row" key={name}><Link href={href} className="mono"><Icon name="folder" size={17} />{name}</Link><span>{description}</span><Link href={href} className="text-link">打开文档 <Icon name="arrow" size={15} /></Link></div>)}</div></section>
      <section id="minimum-example" className="doc-section split-section"><div><SectionHeading id="minimum-example">下一步：运行一个最小示例</SectionHeading><p>几行代码构建并运行处理链。</p><CodeBlock code={`from waveform_analysis import Context\nfrom waveform_analysis.plugins import profiles\n\nctx = Context(config={\n    "data_root": "DAQ",\n    "daq_adapter": "vx2730",\n})\nctx.register(*profiles.cpu_default())\nresult = ctx.get_data("run_001", "records")\nprint(result)`} /></div><aside className="mini-index"><strong>本节内容</strong><Link href="#pipeline">处理链概览</Link><Link href="#workflows">按工作流查找</Link><Link href="#minimum-example">运行最小示例</Link><Link href="#concepts">相关概念</Link></aside></section>
      <section id="concepts" className="doc-section home-links"><SectionHeading id="concepts">相关概念</SectionHeading><div className="link-grid"><Link href="/architecture/data-products/"><span>记录与事件</span><Icon name="arrow" size={17} /></Link><Link href="/architecture/system/"><span>时间与坐标系</span><Icon name="arrow" size={17} /></Link><Link href="/plugins/records/"><span>数据产物</span><Icon name="arrow" size={17} /></Link><Link href="/contexts/context/"><span>配置与可复现性</span><Icon name="arrow" size={17} /></Link></div></section>
      <footer className="home-footer"><span>{siteModel.plugins.length} 个插件 · 本地静态文档</span><Link href="/development/">下一步：开发者指南 <Icon name="arrow" size={15} /></Link></footer>
    </article>
  </SiteShell>;
}
