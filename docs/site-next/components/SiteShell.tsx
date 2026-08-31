"use client";

import { StaticLink as Link } from "./StaticLink";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { SiteShellModel } from "@/lib/search";
import { iconNames, Icon, type IconName } from "./icons";

export type TocItem = { id: string; label: string };

const headerLinks = [
  ["文档", "/"],
  ["插件", "/plugins/"],
  ["Context", "/contexts/context/"],
  ["Accessor", "/accessors/"],
  ["可视化", "/visualizations/"],
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href.replace(/\/$/, "")}/`);
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return <Link className={`brand${compact ? " brand--compact" : ""}`} href="/" aria-label="WaveformAnalysis 首页">
    <img src="/assets/waveform-mark.svg" width="52" height="30" alt="" />
    <span>WaveformAnalysis</span>
  </Link>;
}

function SearchDialog({ model, onClose }: { model: SiteShellModel; onClose: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const entries = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return model.search.slice(0, 8);
    return model.search.filter((entry) => `${entry.title} ${entry.summary} ${entry.keywords}`.toLocaleLowerCase().includes(normalized)).slice(0, 12);
  }, [model, query]);

  useEffect(() => { inputRef.current?.focus(); }, []);

  return <div className="search-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="search-dialog" role="dialog" aria-modal="true" aria-labelledby="search-title">
      <div className="search-dialog__head">
        <div><h2 id="search-title">搜索文档</h2></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="关闭搜索"><Icon name="close" size={20} /></button>
      </div>
      <label className="search-input search-input--dialog">
        <Icon name="search" size={19} />
        <input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索插件、Context 或指南" aria-label="搜索插件、Context 或指南" />
        <kbd>ESC</kbd>
      </label>
      <div className="search-results" aria-live="polite">
        {entries.length ? entries.map((entry) => <Link key={`${entry.kind}:${entry.url}`} href={entry.url} onClick={onClose} className="search-result">
          <span className="search-result__kind">{entry.kind}</span><span><strong>{entry.title}</strong><small>{entry.summary}</small></span><Icon name="arrow" size={16} />
        </Link>) : <p className="empty-state">没有匹配的文档。试试 `records` 或 `Context`。</p>}
      </div>
      <footer className="search-dialog__footer"><span><kbd>↵</kbd> 打开结果</span><span><kbd>ESC</kbd> 关闭</span></footer>
    </section>
  </div>;
}

function SideNav({ model, pathname, onNavigate }: { model: SiteShellModel; pathname: string; onNavigate?: () => void }) {
  const [openSections, setOpenSections] = useState(() => new Set(model.navigation.map((section) => section.id)));
  return <nav className="side-nav" aria-label="文档导航">
    {model.navigation.map((section) => {
      const open = openSections.has(section.id);
      return <section key={section.id} className="side-nav__section">
        <button className="side-nav__heading" type="button" aria-expanded={open} onClick={() => setOpenSections((current) => { const next = new Set(current); if (next.has(section.id)) next.delete(section.id); else next.add(section.id); return next; })}>
          <span>{section.title}</span><Icon name="chevron" size={15} className={open ? "chevron--down" : ""} />
        </button>
        {open && <div className="side-nav__items">{section.items.map((item) => <Link key={`${section.id}:${item.href}:${item.label}`} href={item.href} onClick={onNavigate} className={`side-nav__item${isActive(pathname, item.href) ? " is-active" : ""}`}>
          <Icon name={iconNames.has(item.icon as IconName) ? item.icon as IconName : "file"} size={16} /><span>{item.label}</span>
        </Link>)}</div>}
      </section>;
    })}
    <div className="side-nav__version"><span>版本</span><button type="button" aria-label="选择文档版本">{model.project.version} <Icon name="chevron" size={14} /></button></div>
  </nav>;
}

function TableOfContents({ items }: { items: TocItem[] }) {
  return <aside className="toc" aria-label="本页目录">
    <h2>本页内容</h2>
    {items.length ? <nav>{items.map((item, index) => <a key={item.id} href={`#${item.id}`} className={index === 0 ? "is-current" : ""}>{item.label}</a>)}</nav> : <p>滚动查看本页内容</p>}
  </aside>;
}

export function SiteShell({ model, children, toc = [], title = "文档", compactNav = false, fullBleed = false }: { model: SiteShellModel; children: ReactNode; toc?: TocItem[]; title?: string; compactNav?: boolean; fullBleed?: boolean }) {
  const pathname = usePathname() ?? "/";
  const [searchOpen, setSearchOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("waveform-docs-theme");
      if (stored === "dark" || stored === "light") {
        setTheme(stored);
        document.documentElement.dataset.theme = stored === "dark" ? "dark" : "light";
      }
    } catch {
      // Private browsing and disabled storage should not block reading docs.
    }
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); }
      if (event.key === "Escape") { setSearchOpen(false); setDrawerOpen(false); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next === "dark" ? "dark" : "light";
    try { window.localStorage.setItem("waveform-docs-theme", next); } catch { /* storage is optional */ }
  };

  return <div className={`site-root${fullBleed ? " site-root--full-bleed" : ""}`}>
    <header className="topbar">
      <div className="topbar__brand"><Brand /></div>
      <nav className="topbar__links" aria-label="主导航">{headerLinks.map(([label, href]) => <Link key={href} href={href} className={isActive(pathname, href) ? "is-active" : ""}>{label}</Link>)}</nav>
      <div className="topbar__actions">
        <button className="search-input search-input--trigger" type="button" onClick={() => setSearchOpen(true)} aria-label="搜索文档">
          <Icon name="search" size={18} /><span>搜索文档</span><kbd>⌘K</kbd>
        </button>
        <button className="icon-button topbar__theme" type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "切换浅色主题" : "切换深色主题"} aria-pressed={theme === "dark"}><Icon name={theme === "dark" ? "sun" : "moon"} size={19} /></button>
        <span className="topbar__rule" aria-hidden="true" />
        <a className="icon-button" href="https://github.com/SnowingWolf/WaveformAnalysis" aria-label="在 GitHub 打开 WaveformAnalysis"><Icon name="github" size={21} /></a>
        <button className="icon-button topbar__menu" type="button" onClick={() => setDrawerOpen(true)} aria-label="打开导航"><Icon name="menu" size={27} /></button>
      </div>
    </header>
    <div className="site-progress" aria-hidden="true" />
    <div className="site-layout">
      <aside className={`left-rail${compactNav ? " left-rail--compact" : ""}`}><SideNav model={model} pathname={pathname} /></aside>
      {drawerOpen && <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setDrawerOpen(false); }}><aside className="mobile-drawer" aria-label="移动端文档导航"><div className="mobile-drawer__head"><Brand compact /><button className="icon-button" type="button" onClick={() => setDrawerOpen(false)} aria-label="关闭导航"><Icon name="close" size={22} /></button></div><SideNav model={model} pathname={pathname} onNavigate={() => setDrawerOpen(false)} /></aside></div>}
      <main className="main-column" id="main-content" tabIndex={-1}>{children}</main>
      <TableOfContents items={toc} />
    </div>
    <nav className="mobile-bottom-bar" aria-label="移动端快捷操作">
      <Link href="/" className={pathname === "/" ? "is-active" : ""}><Icon name="book" size={20} /><span>文档</span></Link>
      <button type="button" onClick={() => setSearchOpen(true)}><Icon name="search" size={20} /><span>搜索</span></button>
      <button type="button" onClick={() => setDrawerOpen(true)}><Icon name="menu" size={20} /><span>目录</span></button>
    </nav>
    {searchOpen && <SearchDialog model={model} onClose={() => setSearchOpen(false)} />}
    <span className="sr-only" aria-live="polite">{title} · {model.project.version}</span>
  </div>;
}
