import { StaticLink as Link } from "@/components/StaticLink";
import { CodeBlock, SectionHeading } from "@/components/DocPage";
import { Icon } from "@/components/icons";
import { PipelineFigure, type PipelineStage } from "@/components/PipelineFigure";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export default function HomePage() {
  const siteModel = loadSiteModel();
  const stages: { id: string; title: string; description: string; kind: PipelineStage; products: string[] }[] = [
    { id: "records", title: "采集与记录", description: "解析采集文件，以时间和板卡/通道定位记录，再通过索引读取波形池。", kind: "records", products: ["raw_files", "records", "wave_pool"] },
    { id: "hit_threshold", title: "阈值检测", description: "相对基线、按信号极性判定过阈区间；每段区间形成一个 hit。", kind: "threshold", products: ["hit_threshold"] },
    { id: "hit_merged", title: "同通道合并", description: "按间隔与总宽限制合并同通道、同 dt 的 hit。默认合并间隔为 0。", kind: "merge", products: ["hit_merged"] },
    { id: "peaklets", title: "跨通道聚合", description: "按时间窗口组织不同通道的 hit 区间，汇总成员、起止时间与通道数。", kind: "aggregate", products: ["peaklet_components", "peaklets"] },
    { id: "peaks", title: "波形与分类", description: "重建并求和成员波形，提取面积和时序特征，再按配置分类；默认未设置分类规则。", kind: "features", products: ["peaklet_waveforms", "peaks", "peak_classification"] },
    { id: "s1_s2_pairs", title: "配对与事件", description: "在漂移时间窗内生成候选，再标记 selected。默认按 center_time 配对；选中项结合位置形成事件。", kind: "pairs", products: ["s1_s2_pair_candidates", "s1_s2_pairs", "events"] },
  ];
  const chain = stages.map((stage) => ({
    ...stage,
    href: siteModel.plugins.find((entry) => entry.provides === stage.id)!.route,
    links: stage.products.map((product) => siteModel.plugins.find((entry) => entry.provides === product)!),
  }));
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
        <p className="section-lede">沿当前处理链，查看波形、时间区间和配对关系如何逐步形成。以下为算法示意，非实测、非比例。</p>
        <ol className="pipeline-diagram" aria-label="数据处理的六个主要阶段">
          {chain.map(({ id, title, description, kind, href, links }, index) => <li className="pipeline-step" key={id}>
            <article className="pipeline-card">
              <Link href={href} className="pipeline-card__main">
                <div className="pipeline-card__top"><span className="pipeline-number">0{index + 1}</span><Icon name="arrow" size={17} /></div>
                <div className="pipeline-graphic"><PipelineFigure stage={kind} /></div>
                <h3>{title}</h3><p>{description}</p>
              </Link>
              <div className="pipeline-products" aria-label={`${title}相关产物`}>
                {links.map((plugin) => <Link href={plugin.route} key={plugin.provides}>{plugin.provides}</Link>)}
              </div>
            </article>
          </li>)}
        </ol>
        <p className="pipeline-note">跨通道聚合阶段只组织区间；波形求和在后续进行。配对默认 center_time 为 50% 面积时刻，未选候选仍保留，且不保证全局一对一。中间产物与分支请查看完整依赖图。</p>
      </section>
      <section className="doc-section"><SectionHeading id="workflows">按工作流查找</SectionHeading><div className="workflow-table"><div className="workflow-table__head"><span>工作流</span><span>描述</span><span>入口</span></div>{workflows.map(([name, description, href]) => <div className="workflow-table__row" key={name}><Link href={href} className="workflow-name"><Icon name="folder" size={17} />{name}</Link><span>{description}</span><Link href={href} className="text-link">打开文档 <Icon name="arrow" size={15} /></Link></div>)}</div></section>
      <section className="doc-section"><SectionHeading id="minimum-example">运行一个最小示例</SectionHeading><p>注册默认插件，通过 run_id 和目标产物读取数据。</p><CodeBlock code={`from waveform_analysis import Context\nfrom waveform_analysis.plugins import profiles\n\nctx = Context(config={\n    "data_root": "DAQ",\n    "daq_adapter": "vx2730",\n})\nctx.register(*profiles.cpu_default())\nresult = ctx.get_data("run_001", "records")\nprint(result)`} /></section>
      <section className="doc-section home-links"><SectionHeading id="concepts">相关概念</SectionHeading><div className="link-grid"><Link href="/architecture/data-products/"><span>记录与事件</span><Icon name="arrow" size={17} /></Link><Link href="/architecture/system/"><span>时间与坐标系</span><Icon name="arrow" size={17} /></Link><Link href="/plugins/records/"><span>数据产物</span><Icon name="arrow" size={17} /></Link><Link href="/contexts/context/"><span>配置与可复现性</span><Icon name="arrow" size={17} /></Link></div></section>
      <footer className="home-footer"><span>{siteModel.plugins.length} 个插件 · 本地静态文档</span><Link href="/development/">下一步：开发者指南 <Icon name="arrow" size={15} /></Link></footer>
    </article>
  </SiteShell>;
}
