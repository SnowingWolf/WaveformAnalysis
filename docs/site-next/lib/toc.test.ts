import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { guideTocItems, TableOfContents, type TocItem } from "../components/TableOfContents";

const render = (items: TocItem[]) => renderToStaticMarkup(createElement(TableOfContents, { items }));

describe("page table of contents", () => {
  it("uses the same title heading levels as the guide body, with h2 for an introduction", () => {
    expect(guideTocItems([
      { id: "intro", title: "Intro", paragraphs: [], blocks: [{ kind: "heading", text: "Unrelated", heading_level: 4 }] },
      { id: "detail", title: "Detail", paragraphs: [], blocks: [{ kind: "heading", text: "Detail", heading_level: 3 }] },
    ])).toEqual([{ id: "intro", label: "Intro", level: 2 }, { id: "detail", label: "Detail", level: 3 }]);
  });

  it("nests subsections under their preceding parent, including skipped levels, then returns to root", () => {
    const html = render([
      { id: "parent", label: "Parent", level: 2 },
      { id: "child", label: "Child", level: 3 },
      { id: "deep", label: "Deep", level: 5 },
      { id: "sibling", label: "Sibling", level: 3 },
      { id: "next", label: "Next", level: 2 },
    ]);
    expect(html).toContain('<a href="#child">Child</a><ul class="toc__children"><li><a href="#deep">Deep</a></li></ul></li><li><a href="#sibling">Sibling</a></li></ul></li><li><a href="#next">Next</a>');
    for (const id of ["parent", "child", "deep", "sibling", "next"]) expect(html.match(new RegExp(`href="#${id}"`, "g"))).toHaveLength(1);
  });

  it("keeps unlevelled reference sections as siblings and supports empty pages", () => {
    expect(render([{ id: "one", label: "One" }, { id: "two", label: "Two" }])).not.toContain('class="toc__children"');
    expect(render([])).toContain("滚动查看本页内容");
  });
});
