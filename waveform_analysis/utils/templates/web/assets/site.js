(() => {
  const input = document.querySelector("#plugin-search");
  const cards = [...document.querySelectorAll(".plugin-card")];
  const pluginSets = [...document.querySelectorAll("[data-plugin-set]")];
  const status = document.querySelector("#search-status");
  if (input && status) {
    const update = () => {
      const query = input.value.trim().toLocaleLowerCase();
      let visible = 0;
      for (const card of cards) {
        const match = !query || card.dataset.search.toLocaleLowerCase().includes(query);
        card.hidden = !match;
        if (match) visible += 1;
      }
      for (const pluginSet of pluginSets) {
        pluginSet.hidden = ![...pluginSet.querySelectorAll(".plugin-card")].some(
          (card) => !card.hidden,
        );
      }
      status.textContent = `共 ${visible} 个插件`;
    };
    input.addEventListener("input", update);
  }

  for (const layout of document.querySelectorAll("[data-detail-layout]")) {
    const toggle = layout.querySelector("[data-detail-sidebar-toggle]");
    const label = layout.querySelector("[data-detail-sidebar-label]");
    if (!toggle || !label) continue;
    toggle.addEventListener("click", () => {
      const collapsed = layout.dataset.sidebarCollapsed !== "true";
      layout.dataset.sidebarCollapsed = String(collapsed);
      toggle.setAttribute("aria-expanded", String(!collapsed));
      label.textContent = collapsed ? "显示目录" : "隐藏目录";
    });
  }

  const workspace = document.querySelector(".lineage-workspace[data-lineage-details]");
  const overview = document.querySelector("#plugin-global-lineage");
  if (workspace && overview && window.Plotly) {
    const detailTitle = workspace.querySelector("[data-lineage-detail-title]");
    const detailEmpty = workspace.querySelector("[data-lineage-detail-empty]");
    const detailLink = workspace.querySelector("[data-lineage-detail-link]");
    const detailPlot = workspace.querySelector("[data-lineage-detail-plot]");
    const closeButton = workspace.querySelector("[data-lineage-detail-close]");
    const viewControls = [...document.querySelectorAll("[data-lineage-view]")];
    const embeddedDetails = document.querySelector("#lineage-details-data");
    const embeddedOverviews = document.querySelector("#lineage-overviews-data");
    const terminalOutputs = new Set(
      (workspace.dataset.terminalOutputs || "").split(",").filter(Boolean),
    );
    let detailFigures = embeddedDetails
      ? Promise.resolve(JSON.parse(embeddedDetails.textContent))
      : undefined;
    let overviewFigures = embeddedOverviews
      ? Promise.resolve(JSON.parse(embeddedOverviews.textContent))
      : undefined;
    let selected;
    let activeView = "core";
    const selectedLine = "#b45309";
    const defaultLine = "#087f5b";

    const resizeDetailPlot = () => {
      if (detailPlot?.data && !detailPlot.hidden) Plotly.Plots.resize(detailPlot);
    };
    if (window.ResizeObserver) {
      new ResizeObserver(resizeDetailPlot).observe(detailPlot);
    } else {
      window.addEventListener("resize", resizeDetailPlot);
    }

    const loadDetails = () => {
      if (!detailFigures) {
        detailFigures = fetch(workspace.dataset.lineageDetails).then((response) => {
          if (!response.ok) throw new Error("Unable to load lineage detail data.");
          return response.json();
        });
      }
      return detailFigures;
    };

    const loadOverviews = () => {
      if (!overviewFigures) {
        overviewFigures = fetch(workspace.dataset.lineageOverviews).then((response) => {
          if (!response.ok) throw new Error("Unable to load lineage overview data.");
          return response.json();
        });
      }
      return overviewFigures;
    };

    const updateUrl = (view, provides, replace = false) => {
      const url = new URL(window.location.href);
      url.searchParams.set("view", view);
      if (provides) url.searchParams.set("focus", provides);
      else url.searchParams.delete("focus");
      window.history[replace ? "replaceState" : "pushState"]({}, "", url);
    };

    const highlight = (provides) => {
      const indices = overview.layout?.meta?.node_shape_indices || {};
      const updates = {};
      for (const [name, index] of Object.entries(indices)) {
        updates[`shapes[${index}].line.color`] = name === provides ? selectedLine : defaultLine;
        updates[`shapes[${index}].line.width`] = name === provides ? 3 : 1.5;
      }
      Plotly.relayout(overview, updates);
    };

    const clearSelection = () => {
      selected = undefined;
      highlight();
      detailTitle.textContent = "选择一个插件";
      detailEmpty.hidden = false;
      detailLink.hidden = true;
      detailPlot.hidden = true;
      detailPlot.replaceChildren();
    };

    const renderView = async (view) => {
      const figures = await loadOverviews();
      const figure = figures[view];
      if (!figure) throw new Error(`Unknown lineage view: ${view}`);
      activeView = view;
      for (const control of viewControls) {
        const active = control.dataset.lineageView === view;
        control.classList.toggle("is-active", active);
        control.setAttribute("aria-pressed", String(active));
      }
      await Plotly.react(overview, figure.data, figure.layout, {
        displaylogo: false, responsive: true, scrollZoom: true,
      });
    };

    const selectPlugin = async (provides) => {
      if (!provides || !overview.layout?.meta?.node_shape_indices?.[provides] && overview.layout?.meta?.node_shape_indices?.[provides] !== 0) {
        clearSelection();
        return;
      }
      selected = provides;
      highlight(provides);
      detailTitle.textContent = provides;
      detailEmpty.hidden = true;
      detailLink.href = `${workspace.dataset.pluginPrefix || "plugins/"}${provides}.html`;
      detailLink.hidden = false;
      detailPlot.hidden = false;
      try {
        const figures = await loadDetails();
        if (selected !== provides) return;
        const figure = figures[provides];
        if (!figure) throw new Error("Lineage detail is unavailable.");
        const detailBounds = detailPlot.getBoundingClientRect();
        const detailLayout = {
          ...figure.layout,
          autosize: false,
          width: Math.max(320, Math.floor(detailBounds.width)),
          height: Math.max(360, Math.floor(detailBounds.height)),
          margin: { l: 12, r: 12, t: 52, b: 12 },
        };
        await Plotly.react(detailPlot, figure.data, detailLayout, {
          displaylogo: false,
          responsive: true,
          scrollZoom: true,
        });
        resizeDetailPlot();
      } catch (error) {
        if (selected !== provides) return;
        detailEmpty.textContent = "无法加载谱系详情。";
        detailEmpty.hidden = false;
        detailPlot.hidden = true;
      }
    };

    const restoreState = async ({ push = false, replace = false } = {}) => {
      const params = new URLSearchParams(window.location.search);
      let view = params.get("view") === "all" ? "all" : "core";
      const focus = params.get("focus");
      if (focus && terminalOutputs.has(focus)) view = "all";
      await renderView(view);
      await selectPlugin(focus);
      if (push || replace || (focus && terminalOutputs.has(focus) && params.get("view") !== "all")) {
        updateUrl(view, selected, replace || !push);
      }
    };

    overview.on("plotly_click", (event) => {
      const provides = event.points[0]?.customdata;
      if (provides) selectPlugin(provides).then(() => updateUrl(activeView, selected));
    });
    for (const control of viewControls) {
      control.addEventListener("click", async () => {
        const requested = control.dataset.lineageView;
        if (requested === activeView) return;
        if (requested === "core" && terminalOutputs.has(selected)) clearSelection();
        await renderView(requested);
        await selectPlugin(selected);
        updateUrl(activeView, selected);
      });
    }
    closeButton?.addEventListener("click", () => {
      clearSelection();
      updateUrl(activeView);
    });
    window.addEventListener("popstate", () => restoreState());
    restoreState({ replace: true });
  }

  const focus = new URLSearchParams(window.location.search).get("focus");
  for (const section of document.querySelectorAll(".lineage-section")) {
    const graph = section.querySelector(".lineage-graph");
    const viewport = section.querySelector("[data-lineage-viewport]");
    const scroll = section.querySelector(".lineage-scroll");
    if (!graph || !viewport || !scroll) continue;

    const { width: viewWidth, height: viewHeight } = graph.viewBox.baseVal;
    let zoom = 1;
    const applyZoom = () => {
      const x = (viewWidth * (1 - zoom)) / 2;
      const y = (viewHeight * (1 - zoom)) / 2;
      viewport.setAttribute("transform", `translate(${x} ${y}) scale(${zoom})`);
    };
    for (const control of section.querySelectorAll("[data-lineage-zoom]")) {
      control.addEventListener("click", () => {
        const action = control.dataset.lineageZoom;
        zoom = action === "in" ? Math.min(2.5, zoom + 0.25) : action === "out" ? Math.max(0.5, zoom - 0.25) : 1;
        applyZoom();
      });
    }

    if (!focus) continue;
    const node = section.querySelector(`[data-lineage-node="plugin:${CSS.escape(focus)}"]`);
    if (!node) continue;
    node.classList.add("is-focused");
    const box = node.getBBox();
    const scaleX = graph.clientWidth / viewWidth;
    const scaleY = graph.clientHeight / viewHeight;
    scroll.scrollLeft = Math.max(0, box.x * scaleX - (scroll.clientWidth - box.width * scaleX) / 2);
    scroll.scrollTop = Math.max(0, box.y * scaleY - (scroll.clientHeight - box.height * scaleY) / 2);
  }

  const nav = document.querySelector("[data-doc-nav]");
  const navOpen = document.querySelector("[data-doc-nav-open]");
  const navClose = nav?.querySelector("[data-doc-nav-close]");
  const setNavigation = (open) => {
    if (!nav || !navOpen) return;
    nav.classList.toggle("is-open", open);
    navOpen.setAttribute("aria-expanded", String(open));
    if (open) navClose?.focus();
    else navOpen.focus();
  };
  navOpen?.addEventListener("click", () => setNavigation(true));
  navClose?.addEventListener("click", () => setNavigation(false));
  for (const toggle of document.querySelectorAll("[data-tree-toggle]")) {
    const target = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!target) continue;
    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(expanded));
      target.hidden = !expanded;
    });
  }

  const themeToggle = document.querySelector("[data-theme-toggle]");
  const syncThemeToggle = () => {
    const dark = document.documentElement.dataset.theme === "dark";
    themeToggle?.setAttribute("aria-label", dark ? "切换到浅色主题" : "切换到深色主题");
    themeToggle?.setAttribute("title", dark ? "切换到浅色主题" : "切换到深色主题");
  };
  syncThemeToggle();
  themeToggle?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("waveform-docs-theme", next); } catch (_) {}
    syncThemeToggle();
  });

  const dialog = document.querySelector("[data-search-dialog]");
  const openSearch = document.querySelector("[data-search-open]");
  const closeSearch = dialog?.querySelector("[data-search-close]");
  const searchInput = dialog?.querySelector("[data-site-search-input]");
  const searchStatus = dialog?.querySelector("[data-site-search-status]");
  const searchResults = dialog?.querySelector("[data-site-search-results]");
  const rootPrefix = document.body.dataset.siteRootPrefix || "";
  const renderSearch = () => {
    if (!searchInput || !searchStatus || !searchResults) return;
    const query = searchInput.value.trim().toLocaleLowerCase();
    searchResults.replaceChildren();
    if (!query) {
      searchStatus.textContent = "输入关键词开始搜索。";
      return;
    }
    const entries = (window.WAVEFORM_DOCS_SEARCH || []).filter((entry) =>
      `${entry.title} ${entry.summary} ${entry.keywords}`.toLocaleLowerCase().includes(query),
    ).slice(0, 12);
    searchStatus.textContent = entries.length ? `找到 ${entries.length} 个结果。` : "没有匹配结果。";
    for (const entry of entries) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = `${rootPrefix}${entry.url}`;
      const kind = document.createElement("span");
      kind.className = "site-search-kind";
      kind.textContent = entry.kind;
      const title = document.createElement("strong");
      title.textContent = entry.title;
      const summary = document.createElement("span");
      summary.textContent = entry.summary;
      link.append(kind, title, summary);
      item.append(link);
      searchResults.append(item);
    }
  };
  const showSearch = () => {
    if (!dialog) return;
    dialog.showModal();
    searchInput?.focus();
  };
  openSearch?.addEventListener("click", showSearch);
  closeSearch?.addEventListener("click", () => dialog?.close());
  searchInput?.addEventListener("input", renderSearch);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (dialog?.open) dialog.close();
      else if (nav?.classList.contains("is-open")) setNavigation(false);
    }
    if (event.key === "/" && !dialog?.open && !["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
      event.preventDefault();
      showSearch();
    }
  });

  const toc = document.querySelector("[data-page-toc]");
  const tocList = toc?.querySelector("ol");
  const slugify = (value, fallback) => {
    const normalized = value.toLocaleLowerCase().trim().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-").replace(/^-+|-+$/g, "");
    return normalized || fallback;
  };
  const tocTargets = [];
  if (tocList) {
    const usedIds = new Set([...document.querySelectorAll("[id]")].map((element) => element.id));
    for (const heading of document.querySelectorAll(".reference h2, .reference h3")) {
      const section = heading.closest("section[id], article[id]");
      let target = heading.tagName === "H2" && section ? section : heading;
      if (!target.id) {
        const base = slugify(heading.textContent, "section");
        let id = base;
        let index = 2;
        while (usedIds.has(id)) id = `${base}-${index++}`;
        target.id = id;
        usedIds.add(id);
      }
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = `#${target.id}`;
      link.dataset.tocLevel = heading.tagName.slice(1);
      link.textContent = heading.textContent.trim();
      link.addEventListener("click", (event) => {
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", `#${target.id}`);
      });
      item.append(link);
      tocList.append(item);
      tocTargets.push([target, link]);
    }
  }
  if (tocTargets.length && window.IntersectionObserver) {
    const tocLinks = tocTargets.map(([, link]) => link);
    const byId = new Map(tocTargets.map(([target, link]) => [target.id, link]));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      for (const link of tocLinks) {
        const active = link === byId.get(visible.target.id);
        link.classList.toggle("is-active", active);
        if (active) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
    }, { rootMargin: "-80px 0px -65% 0px" });
    for (const [target] of tocTargets) observer.observe(target);
  }
})();
