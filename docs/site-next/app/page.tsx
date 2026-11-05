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
  const stages = [
    { id: "raw_files", title: "原始数据", description: "定位采集文件，按采集格式组织输入。", kind: "raw" },
    { id: "records", title: "波形记录", description: "建立记录索引，关联时间、通道与波形池。", kind: "wave" },
    { id: "hit_threshold", title: "信号检测", description: "识别超过阈值的波形片段，提取 hit。", kind: "wave" },
    { id: "peaklets", title: "跨通道聚合", description: "从合并后的 hit 区间构建轻量 peaklet。", kind: "peak" },
    { id: "peaks", title: "峰特征", description: "汇总峰结构与波形特征，形成 peaks 表。", kind: "peak" },
    { id: "events", title: "事件重建", description: "结合 S1–S2 配对与位置，构建物理事件。", kind: "event" },
  ];
  const chain = stages.flatMap((stage) => {
    const plugin = siteModel.plugins.find((entry) => entry.provides === stage.id);
    return plugin ? [{ ...stage, href: plugin.route }] : [];
  });
  const workflows = siteModel.guides.map((page) => [page.title, page.summary, page.route] as const).slice(0, 5);

  return <SiteShell model={siteModel} title="快速开始" toc={[{ id: "pipeline", label: "处理链概览" }, { id: "workflows", label: "按工作流查找" }, { id: "minimum-example", label: "运行最小示例" }, { id: "concepts", label: "相关概念" }]}>
    <article className="doc-article home-article">
      <header className="home-hero">
        <div className="hero-eyebrow"><span className="hero-eyebrow__dot" />波形处理与物理重建<span className="hero-version">v{siteModel.project.version}</span></div>
        <h1>WaveformAnalysis<span>文档与指南</span></h1>
        <p>从 DAQ 波形到物理事件，<br className="hero-mobile-break" />找到每一步的数据产物与分析方法。</p>
        <div className="hero-actions"><Link className="button button--primary" href="/user-guide/EXAMPLES_GUIDE/">快速开始 <Icon name="arrow" size={17} /></Link><Link className="button button--secondary" href="/lineage/">探索处理链 <Icon name="nodes" size={17} /></Link></div>
      </header>
      <section className="doc-section pipeline-section">
        <div className="section-topline"><SectionHeading id="pipeline">处理链概览</SectionHeading><Link href="/lineage/" className="text-link">完整依赖图 <Icon name="arrow" size={16} /></Link></div>
        <p className="section-lede">六个阶段，了解数据如何从采集文件走向分析结果。</p>
        <ol className="pipeline-diagram" aria-label="数据处理的六个主要阶段">
          {chain.map(({ id, title, description, kind, href }, index) => <li className="pipeline-step" key={id}>
            <Link href={href} className={`pipeline-card pipeline-card--${kind}`}>
              <div className="pipeline-card__top"><span className="pipeline-number">0{index + 1}</span><Icon name="arrow" size={17} /></div>
              <span className="pipeline-graphic"><PipelineGlyph kind={kind} /></span>
              <h3>{title}</h3><strong>{id}</strong><p>{description}</p>
            </Link>
          </li>)}
        </ol>
        <p className="pipeline-note">这是简化的阶段概览；中间产物、分支与真实依赖请查看完整处理链。</p>
      </section>
      <section className="doc-section"><SectionHeading id="workflows">按工作流查找</SectionHeading><div className="workflow-table"><div className="workflow-table__head"><span>工作流</span><span>描述</span><span>入口</span></div>{workflows.map(([name, description, href]) => <div className="workflow-table__row" key={name}><Link href={href} className="workflow-name"><Icon name="folder" size={17} />{name}</Link><span>{description}</span><Link href={href} className="text-link">打开文档 <Icon name="arrow" size={15} /></Link></div>)}</div></section>
      <section className="doc-section"><SectionHeading id="minimum-example">运行一个最小示例</SectionHeading><p>注册默认插件，通过 run_id 和目标产物读取数据。</p><CodeBlock code={`from waveform_analysis import Context\nfrom waveform_analysis.plugins import profiles\n\nctx = Context(config={\n    "data_root": "DAQ",\n    "daq_adapter": "vx2730",\n})\nctx.register(*profiles.cpu_default())\nresult = ctx.get_data("run_001", "records")\nprint(result)`} /></section>
      <section className="doc-section home-links"><SectionHeading id="concepts">相关概念</SectionHeading><div className="link-grid"><Link href="/architecture/data-products/"><span>记录与事件</span><Icon name="arrow" size={17} /></Link><Link href="/architecture/system/"><span>时间与坐标系</span><Icon name="arrow" size={17} /></Link><Link href="/plugins/records/"><span>数据产物</span><Icon name="arrow" size={17} /></Link><Link href="/contexts/context/"><span>配置与可复现性</span><Icon name="arrow" size={17} /></Link></div></section>
      <footer className="home-footer"><span>{siteModel.plugins.length} 个插件 · 本地静态文档</span><Link href="/development/">下一步：开发者指南 <Icon name="arrow" size={15} /></Link></footer>
    </article>
  </SiteShell>;
}
