import type { GuideSection } from "@/lib/site-model";

export type TocItem = { id: string; label: string; level?: 2 | 3 | 4 | 5 | 6 };
type TocNode = TocItem & { children: TocNode[] };

export function guideTocItems(sections: GuideSection[]): TocItem[] {
  return sections.map((section) => {
    const firstBlock = section.blocks[0];
    const titleBlock = firstBlock?.kind === "heading" && firstBlock.text === section.title ? firstBlock : undefined;
    return { id: section.id, label: section.title, level: titleBlock?.heading_level ?? 2 };
  });
}

function tocTree(items: TocItem[]): TocNode[] {
  const roots: TocNode[] = [];
  const parents: TocNode[] = [];
  for (const item of items) {
    const node: TocNode = { ...item, children: [] };
    while (parents.length && (parents[parents.length - 1].level ?? 2) >= (item.level ?? 2)) parents.pop();
    const parent = parents[parents.length - 1];
    (parent ? parent.children : roots).push(node);
    parents.push(node);
  }
  return roots;
}

function TocList({ nodes, firstId, nested = false }: { nodes: TocNode[]; firstId?: string; nested?: boolean }) {
  return <ul className={nested ? "toc__children" : "toc__list"}>{nodes.map((node) => <li key={node.id}>
    <a href={`#${node.id}`} className={node.id === firstId ? "is-current" : undefined}>{node.label}</a>
    {node.children.length > 0 && <TocList nodes={node.children} firstId={firstId} nested />}
  </li>)}</ul>;
}

export function TableOfContents({ items }: { items: TocItem[] }) {
  return <aside className="toc" aria-label="本页目录">
    <h2>本页内容</h2>
    {items.length ? <nav aria-label="章节目录"><TocList nodes={tocTree(items)} firstId={items[0].id} /></nav> : <p>滚动查看本页内容</p>}
  </aside>;
}
