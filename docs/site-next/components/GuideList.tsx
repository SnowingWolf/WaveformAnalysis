import type { ReactNode } from "react";
import type { GuideListNode, InlineContent, ReferenceContentBlock } from "@/lib/site-model";

type InlineRenderer = (content: InlineContent[] | undefined, fallback: string) => ReactNode;

function ListTree({ node, renderInline }: { node: GuideListNode; renderInline: InlineRenderer }) {
  const List = node.ordered ? "ol" : "ul";
  return <List className="reference-list" start={node.ordered ? node.start : undefined}>{node.entries.map((entry, index) =>
    <li key={index}>{renderInline(entry.inlines, entry.text)}{entry.children?.map((child, childIndex) =>
      <ListTree key={childIndex} node={child} renderInline={renderInline} />,
    )}</li>,
  )}</List>;
}

export function GuideList({ block, renderInline }: { block: ReferenceContentBlock; renderInline: InlineRenderer }) {
  const node = block.list_tree ?? {
    ordered: block.ordered ?? false,
    entries: (block.items ?? []).map((text, index) => ({ text, inlines: block.item_inlines?.[index] })),
  };
  return <ListTree node={node} renderInline={renderInline} />;
}
