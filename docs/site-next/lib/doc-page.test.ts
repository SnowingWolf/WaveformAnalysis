import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GuideSections, ReferenceSections } from "../components/DocPage";
import type { GuideSection } from "./site-model";

describe("documentation section HTML", () => {
  it("preserves guide heading levels and gives each existing anchor one target", () => {
    const sections: GuideSection[] = ([2, 3, 4, 5, 6] as const).map((level) => ({
      id: `section-${level}`,
      title: `Title ${level}`,
      paragraphs: [],
      blocks: [
        { kind: "heading", text: `Title ${level}`, heading_level: level },
        { kind: "paragraph", text: `Body ${level}` },
      ],
    }));
    const html = renderToStaticMarkup(createElement(GuideSections, { sections }));
    for (const level of [2, 3, 4, 5, 6]) {
      expect(html).toContain(`<h${level}>Title ${level}</h${level}>`);
      expect(html).toContain(`<section id="section-${level}"`);
      expect(html.match(new RegExp(`id="section-${level}"`, "g"))).toHaveLength(1);
      expect(html.match(new RegExp(`Title ${level}`, "g"))).toHaveLength(1);
      expect(html).toContain(`Body ${level}`);
    }
  });

  it("uses h2 for introductory sections and retains non-title heading blocks", () => {
    const html = renderToStaticMarkup(createElement(GuideSections, {
      sections: [{
        id: "intro", title: "Introduction", paragraphs: [],
        blocks: [{ kind: "heading", heading_level: 4, text: "Detail" }],
      }],
    }));
    expect(html).toContain('<h2>Introduction</h2>');
    expect(html).toContain('<section id="intro"');
    expect(html).toContain('<h4><span>Detail</span></h4>');
  });

  it("retains reference section anchors and h2 titles with nested h3 headings", () => {
    const html = renderToStaticMarkup(createElement(ReferenceSections, {
      sections: [{
        id: "api", title: "API",
        blocks: [{ kind: "heading", heading_level: 2, text: "Parameters" }],
      }],
    }));
    expect(html).toContain('<section id="api"');
    expect(html.match(/id="api"/g)).toHaveLength(1);
    expect(html).toContain('<h2>API</h2>');
    expect(html).toContain('<h3><span>Parameters</span></h3>');
  });

  it("renders nested lists inside their owning items and preserves start numbers and links", () => {
    const html = renderToStaticMarkup(createElement(GuideSections, {
      sections: [{ id: "steps", title: "Steps", paragraphs: [], blocks: [{
        kind: "list", list_tree: {
          ordered: true, start: 3, entries: [{
            text: "Parent", children: [{ ordered: false, entries: [{
              text: "Child", inlines: [{ kind: "link", text: "Child", href: "/child/" }],
            }] }],
          }, { text: "Next" }],
        },
      }] }],
    }));
    expect(html).toContain('<ol class="reference-list" start="3"><li><span>Parent</span><ul class="reference-list"><li><a href="/child/"><span>Child</span></a></li></ul></li><li><span>Next</span></li></ol>');
  });

  it("renders legacy flat reference lists through the shared list component", () => {
    const html = renderToStaticMarkup(createElement(ReferenceSections, {
      sections: [{ id: "legacy", title: "Legacy", blocks: [{
        kind: "list", ordered: true, items: ["Use `records`"],
      }] }],
    }));
    expect(html).toContain('<ol class="reference-list"><li><span>Use </span><code class="inline-code">records</code></li></ol>');
  });
});
