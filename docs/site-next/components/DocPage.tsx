import { StaticLink as Link } from "./StaticLink";
import type { ReactNode } from "react";
import type { AccessorModel, ContextModel, PluginModel, SiteModel, VisualizationModel } from "@/lib/site-model";
import { siteShellModel } from "@/lib/search";
import { CopyButton } from "./CopyButton";
import { Icon } from "./icons";
import { SiteShell } from "./SiteShell";

export function Breadcrumbs({ items }: { items: Array<{ label: string; href?: string }> }) {
  return <nav className="breadcrumbs" aria-label="面包屑导航">{items.map((item, index) => <span key={`${item.label}:${index}`}>{item.href ? <Link href={item.href}>{item.label}</Link> : <span aria-current="page">{item.label}</span>}{index < items.length - 1 && <b>/</b>}</span>)}</nav>;
}

export function SectionHeading({ id, children, note }: { id?: string; children: ReactNode; note?: string }) {
  return <div className="section-heading">{id && <span className="section-heading__mark" aria-hidden="true" />}<div>{<h2 id={id}>{children}</h2>}{note && <p>{note}</p>}</div></div>;
}

export function CodeBlock({ code, language = "python" }: { code: string; language?: string }) {
  return <div className="code-block"><div className="code-block__bar"><span>{language}</span><CopyButton value={code} /></div><pre><code>{code}</code></pre></div>;
}

export function DataTable({ headers, rows, caption }: { headers: string[]; rows: string[][]; caption?: string }) {
  return <div className="data-table-wrap"><table className="data-table"><caption className="sr-only">{caption ?? "数据表"}</caption><thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row[0] ?? "row"}:${index}`}>{headers.map((_, cellIndex) => <td key={`${cellIndex}:${row[cellIndex] ?? ""}`}>{row[cellIndex] ?? "—"}</td>)}</tr>)}</tbody></table></div>;
}

function PageIntro({ title, subtitle, chips, relation }: { title: string; subtitle: string; chips?: string[]; relation?: { from: string; to: string } }) {
  return <header className="page-intro"><h1>{title}</h1><p className="page-intro__subtitle">{subtitle}</p>{chips && <div className="chip-row">{chips.map((chip, index) => <span className={`chip${index === 0 ? " chip--accent" : ""}`} key={chip}>{chip}</span>)}</div>}{relation && <div className="relation-strip"><span className="mono">{relation.from}</span><Icon name="arrow" size={25} /><span className="mono relation-strip__target">{relation.to}</span></div>}</header>;
}

type CallablePage = ContextModel | AccessorModel;

function callableToc(page: CallablePage, kind: "Context" | "Accessor") {
  const profiles = "profiles" in page ? page.profiles : [];
  const examples = "examples" in page ? page.examples : [];
  const methods = "methods" in page ? page.methods : [];
  return [{ id: "overview", label: "概览" }, ...(kind === "Context" && profiles.length ? [{ id: "profiles", label: "Profiles" }] : []), ...(kind === "Context" && examples.length ? [{ id: "example", label: "快速使用" }] : []), ...(kind === "Accessor" && methods.length ? [{ id: "methods", label: "方法" }] : [])];
}

export function CallableReferencePage({ model, page, kind }: { model: SiteModel; page: CallablePage; kind: "Context" | "Accessor" }) {
  const toc = callableToc(page, kind);
  const profiles = "profiles" in page ? page.profiles : [];
  const examples = "examples" in page ? page.examples : [];
  const inputs = "inputs" in page ? page.inputs : [];
  const methods = "methods" in page ? page.methods : [];
  const code = examples[0] ?? "from waveform_analysis import Context\n\nctx = Context(config={\"data_root\": \"DAQ\"})\nresult = ctx.get_data(\"run_001\", \"records\")";
  return <SiteShell model={siteShellModel(model)} toc={toc} title={page.name}>
    <article className="doc-article">
      <Breadcrumbs items={[{ label: kind, href: kind === "Context" ? "/contexts/" : "/accessors/" }, { label: page.name }]} />
      <PageIntro title={page.name} subtitle={page.summary} />
      <section id="overview" className="doc-section"><SectionHeading id="overview">概览</SectionHeading><p>{page.summary}</p></section>
      {kind === "Context" && profiles.length > 0 && <section id="profiles" className="doc-section"><SectionHeading id="profiles">Profiles</SectionHeading><div className="signal-list">{profiles.map((profile) => <span key={profile}><Icon name="layers" size={15} />{profile}</span>)}</div></section>}
      {kind === "Accessor" && methods.length > 0 && <section id="methods" className="doc-section"><SectionHeading id="methods">方法</SectionHeading><DataTable headers={["方法", "输入"]} rows={methods.map((method) => [method, inputs.join(", ") || "—"])} caption={`${page.name} 方法`} /></section>}
      {kind === "Context" && examples.length > 0 && <section id="example" className="doc-section"><SectionHeading id="example">快速使用</SectionHeading><CodeBlock code={code} /></section>}
    </article>
  </SiteShell>;
}

export function VisualizationReferencePage({ model, page }: { model: SiteModel; page: VisualizationModel }) {
  return <SiteShell model={siteShellModel(model)} toc={[{ id: "overview", label: "概览" }, { id: "outputs", label: "输出" }, { id: "example", label: "快速使用" }]} title={page.name}>
    <article className="doc-article"><Breadcrumbs items={[{ label: "可视化", href: "/visualizations/" }, { label: page.name }]} /><PageIntro title={page.name} subtitle={page.summary} />
      <section id="overview" className="doc-section"><SectionHeading id="overview">概览</SectionHeading><p>{page.summary}</p></section>
      <section id="outputs" className="doc-section"><SectionHeading id="outputs">输出</SectionHeading><div className="signal-list">{page.outputs.map((output) => <span key={output}><Icon name="check" size={15} />{output}</span>)}</div></section>
      <section id="example" className="doc-section"><SectionHeading id="example">快速使用</SectionHeading><CodeBlock code={`from waveform_analysis.visualization import ${page.slug.replaceAll("-", "_")}\n\nfigure = ${page.slug.replaceAll("-", "_")}(data)`} /></section>
    </article></SiteShell>;
}

export function PluginReferencePage({ model, plugin }: { model: SiteModel; plugin: PluginModel }) {
  const fields = plugin.fields ?? [];
  const config = plugin.config ?? [];
  const fieldRows = fields.map((field) => [field.name, field.dtype, field.unit, field.description]);
  const configRows = config.map((entry) => [entry.name, entry.value, entry.description]);
  const toc = [{ id: "configuration", label: "配置" }, ...(fields.length ? [{ id: "output", label: "输出字段" }] : []), { id: "usage", label: "快速使用" }];
  return <SiteShell model={siteShellModel(model)} toc={toc} title={plugin.provides}>
    <article className="doc-article doc-article--plugin">
      <Breadcrumbs items={[{ label: "插件", href: "/plugins/" }, { label: "内置插件", href: "/plugins/" }, { label: plugin.provides }]} />
      <PageIntro title={plugin.provides} subtitle={plugin.pluginClass ?? "内置插件"} chips={[`v${plugin.version}`, plugin.executionKind, plugin.outputKind]} relation={plugin.dependsOn?.[0] ? { from: plugin.dependsOn[0], to: plugin.provides } : undefined} />
      <p className="lede">{plugin.summary}</p>
      <section id="configuration" className="doc-section"><SectionHeading id="configuration">配置</SectionHeading>{configRows.length ? <DataTable headers={["参数", "默认值", "说明"]} rows={configRows} caption={`${plugin.provides} 配置`} /> : <p className="muted">该插件没有额外配置项。</p>}</section>
      {fieldRows.length > 0 && <section id="output" className="doc-section"><SectionHeading id="output">输出字段</SectionHeading><DataTable headers={["字段名", "类型", "单位", "说明"]} rows={fieldRows} caption={`${plugin.provides} 输出字段`} /></section>}
      <section id="usage" className="doc-section"><SectionHeading id="usage">快速使用</SectionHeading><CodeBlock code={plugin.usage} /></section>
      <aside className="callout"><div className="callout__icon"><Icon name="layers" size={18} /></div><div><strong>处理链位置</strong><p>在处理链中查看该插件的输入、输出和下游消费者。</p><Link href={`/lineage/?focus=${encodeURIComponent(plugin.provides)}`}>打开处理链 <Icon name="arrow" size={15} /></Link></div></aside>
    </article>
  </SiteShell>;
}
