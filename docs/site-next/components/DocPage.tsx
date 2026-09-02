import { StaticLink as Link } from "./StaticLink";
import type { ReactNode } from "react";
import type { AccessorModel, ContextModel, GuideSection, InlineContent, PluginModel, ReferenceContentBlock, ReferenceSection, SiteModel, VisualizationModel } from "@/lib/site-model";
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

export function InlineText({ text }: { text: string }) {
  return <>{text.split(/(`[^`]+`)/g).filter(Boolean).map((part, index) => part.startsWith("`") && part.endsWith("`") ? <code className="inline-code" key={`${part}:${index}`}>{part.slice(1, -1)}</code> : <span key={`${part}:${index}`}>{part}</span>)}</>;
}

function InlineContentView({ content, fallback }: { content?: InlineContent[]; fallback: string }) {
  if (!content?.length) return <InlineText text={fallback} />;
  return <>{content.map((part, index) => {
    const key = `${part.kind}:${part.text}:${index}`;
    if (part.kind === "code") return <code className="inline-code" key={key}>{part.text}</code>;
    if (part.kind === "link" && part.href) return <Link href={part.href} key={key}><InlineText text={part.text} /></Link>;
    if (part.kind === "image" && part.href) return <Link href={part.href} key={key}><InlineText text={part.text} /></Link>;
    return <span key={key}>{part.text}</span>;
  })}</>;
}

export function DataTable({ headers, rows, caption }: { headers: string[]; rows: string[][]; caption?: string }) {
  return <div className="data-table-wrap"><table className="data-table"><caption className="sr-only">{caption ?? "数据表"}</caption><thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row[0] ?? "row"}:${index}`}>{headers.map((_, cellIndex) => <td key={`${cellIndex}:${row[cellIndex] ?? ""}`}><InlineText text={row[cellIndex] ?? "—"} /></td>)}</tr>)}</tbody></table></div>;
}

function PageIntro({ title, subtitle, chips, relation }: { title: string; subtitle: string; chips?: string[]; relation?: { from: string; to: string } }) {
  return <header className="page-intro"><h1>{title}</h1><p className="page-intro__subtitle">{subtitle}</p>{chips && <div className="chip-row">{chips.map((chip, index) => <span className={`chip${index === 0 ? " chip--accent" : ""}`} key={chip}>{chip}</span>)}</div>}{relation && <div className="relation-strip"><span className="mono">{relation.from}</span><Icon name="arrow" size={25} /><span className="mono relation-strip__target">{relation.to}</span></div>}</header>;
}

function ContentBlockView({ block }: { block: ReferenceContentBlock }) {
  if (block.kind === "paragraph") return <p><InlineContentView content={block.inlines} fallback={block.text ?? ""} /></p>;
  if (block.kind === "heading") {
    const level = block.heading_level ?? 3;
    const Heading = level === 2 ? "h3" : level === 4 ? "h4" : level === 5 ? "h5" : level === 6 ? "h6" : "h3";
    return <Heading><InlineContentView content={block.inlines} fallback={block.text ?? ""} /></Heading>;
  }
  if (block.kind === "list") {
    const List = block.ordered ? "ol" : "ul";
    return <List className="reference-list">{(block.items ?? []).map((item, index) => <li key={`${item}:${index}`}><InlineContentView content={block.item_inlines?.[index]} fallback={item} /></li>)}</List>;
  }
  if (block.kind === "note") return <aside className={`reference-note reference-note--${block.tone ?? "note"}`}>{block.title && <strong>{block.title}</strong>}<p><InlineContentView content={block.inlines} fallback={block.text ?? ""} /></p></aside>;
  if (block.kind === "code") return <CodeBlock code={block.code ?? ""} language={block.language || "text"} />;
  if (block.kind === "table") return <div className="data-table-wrap"><table className="data-table"><caption className="sr-only">数据表</caption><thead><tr>{(block.table_headers ?? []).map((header, index) => <th key={`${header}:${index}`} scope="col"><InlineContentView content={block.table_inlines?.[0]?.[index]} fallback={header} /></th>)}</tr></thead><tbody>{(block.table_rows ?? []).map((row, rowIndex) => <tr key={`row:${rowIndex}`}>{(block.table_headers ?? []).map((_, cellIndex) => <td key={`${rowIndex}:${cellIndex}`}><InlineContentView content={block.table_inlines?.[rowIndex + 1]?.[cellIndex]} fallback={row[cellIndex] ?? "—"} /></td>)}</tr>)}</tbody></table></div>;
  if (block.kind === "mermaid") return <figure className="mermaid-source"><figcaption>流程图定义</figcaption><CodeBlock code={block.mermaid ?? ""} language="mermaid" /></figure>;
  if (block.kind === "image") return <figure className="reference-image"><img src={`/content-assets/${block.image_src ?? ""}`} alt={block.image_alt ?? ""} />{block.image_caption && <figcaption>{block.image_caption}</figcaption>}</figure>;
  if (block.kind === "mathml") return <CodeBlock code={block.mathml ?? ""} language="mathml" />;
  return null;
}

export function ReferenceSections({ sections }: { sections: ReferenceSection[] }) {
  return <>{sections.map((section) => <section id={section.id} className="doc-section reference-section" key={section.id}><SectionHeading>{section.title}</SectionHeading><div className="reference-blocks">{section.blocks.map((block, index) => <ContentBlockView block={block} key={`${section.id}:${block.kind}:${index}`} />)}</div></section>)}</>;
}

export function GuideSections({ sections }: { sections: GuideSection[] }) {
  return <>{sections.map((section) => <section id={section.id} className="doc-section reference-section" key={section.id}><SectionHeading id={section.id}>{section.title}</SectionHeading><div className="reference-blocks">{section.blocks.map((block, index) => index === 0 && block.kind === "heading" && block.text === section.title ? null : <ContentBlockView block={block} key={`${section.id}:${block.kind}:${index}`} />)}</div></section>)}</>;
}

type CallablePage = ContextModel | AccessorModel;

export function CallableReferencePage({ model, page, kind }: { model: SiteModel; page: CallablePage; kind: "Context" | "Accessor" }) {
  const toc = page.sections.map((section) => ({ id: section.id, label: section.title }));
  return <SiteShell model={siteShellModel(model)} toc={toc} title={page.name}>
    <article className="doc-article">
      <Breadcrumbs items={[{ label: kind, href: kind === "Context" ? "/contexts/" : "/accessors/" }, { label: page.name }]} />
      <PageIntro title={page.name} subtitle={page.summary} />
      <ReferenceSections sections={page.sections} />
    </article>
  </SiteShell>;
}

export function VisualizationReferencePage({ model, page }: { model: SiteModel; page: VisualizationModel }) {
  return <SiteShell model={siteShellModel(model)} toc={page.sections.map((section) => ({ id: section.id, label: section.title }))} title={page.name}>
    <article className="doc-article"><Breadcrumbs items={[{ label: "可视化", href: "/visualizations/" }, { label: page.name }]} /><PageIntro title={page.name} subtitle={page.summary} />
      <ReferenceSections sections={page.sections} />
    </article></SiteShell>;
}

export function PluginReferencePage({ model, plugin }: { model: SiteModel; plugin: PluginModel }) {
  const toc = plugin.sections.map((section) => ({ id: section.id, label: section.title }));
  return <SiteShell model={siteShellModel(model)} toc={toc} title={plugin.provides}>
    <article className="doc-article doc-article--plugin">
      <Breadcrumbs items={[{ label: "插件", href: "/plugins/" }, { label: "内置插件", href: "/plugins/" }, { label: plugin.provides }]} />
      <PageIntro title={plugin.provides} subtitle={plugin.pluginClass ?? "内置插件"} chips={[`v${plugin.version}`, plugin.executionKind, plugin.outputKind]} relation={plugin.dependsOn?.[0] ? { from: plugin.dependsOn[0], to: plugin.provides } : undefined} />
      <p className="lede">{plugin.summary}</p>
      <ReferenceSections sections={plugin.sections} />
      <aside className="callout"><div className="callout__icon"><Icon name="layers" size={18} /></div><div><strong>处理链位置</strong><p>在处理链中查看该插件的输入、输出和下游消费者。</p><Link href={`/lineage/?focus=${encodeURIComponent(plugin.provides)}`}>打开处理链 <Icon name="arrow" size={15} /></Link></div></aside>
    </article>
  </SiteShell>;
}
