"use client";

import { StaticLink as Link } from "./StaticLink";
import { useMemo, useState } from "react";
import type { PluginModel } from "@/lib/site-model";
import { Icon } from "./icons";

export function PluginDirectory({ plugins }: { plugins: PluginModel[] }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("全部");
  const categories = ["全部", ...Array.from(new Set(plugins.map((plugin) => plugin.category)))];
  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return plugins.filter((plugin) => (category === "全部" || plugin.category === category) && (!normalized || `${plugin.provides} ${plugin.summary}`.toLocaleLowerCase().includes(normalized)));
  }, [category, plugins, query]);
  return <div className="plugin-directory">
    <div className="directory-tools"><label className="search-input directory-search"><Icon name="search" size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="过滤插件..." aria-label="过滤插件" /></label><div className="filter-tabs" role="tablist" aria-label="按类别过滤">{categories.slice(0, 7).map((item) => <button key={item} type="button" role="tab" aria-selected={category === item} className={category === item ? "is-active" : ""} onClick={() => setCategory(item)}>{item}</button>)}</div></div>
    <div className="directory-meta"><span><strong>{visible.length}</strong> / {plugins.length} 个插件</span><span className="mono">schema: site-model/v1</span></div>
    <div className="plugin-table"><div className="plugin-table__head"><span>插件</span><span>描述</span><span>输出</span><span>版本</span></div>{visible.map((plugin) => <Link className="plugin-table__row" key={plugin.provides} href={plugin.route}><span className="plugin-name"><Icon name="puzzle" size={16} /><strong>{plugin.provides}</strong></span><span>{plugin.summary}</span><span className="mono">{plugin.outputKind}</span><span className="mono">{plugin.version ? `v${plugin.version}` : "—"}</span></Link>)}{visible.length === 0 && <p className="empty-state">没有匹配的插件。</p>}</div>
  </div>;
}
