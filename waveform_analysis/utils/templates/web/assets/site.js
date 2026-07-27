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
    const detailPanel = workspace.querySelector(".lineage-detail");
    const relations = workspace.querySelector("[data-lineage-relations]");
    const inputList = workspace.querySelector("[data-lineage-inputs]");
    const consumerList = workspace.querySelector("[data-lineage-consumers]");
    const closeButton = workspace.querySelector("[data-lineage-detail-close]");
    const viewControls = [...document.querySelectorAll("[data-lineage-view]")];
    const embeddedDetails = document.querySelector("#lineage-details-data");
    const embeddedOverviews = document.querySelector("#lineage-overviews-data");
    const terminalOutputs = new Set(
      (workspace.dataset.terminalOutputs || "").split(",").filter(Boolean),
    );
    let detailRelations = embeddedDetails
      ? Promise.resolve(JSON.parse(embeddedDetails.textContent))
      : undefined;
    let overviewFigures = embeddedOverviews
      ? Promise.resolve(JSON.parse(embeddedOverviews.textContent))
      : undefined;
    let selected;
    let activeView = "core";
    let activeFigure;
    const selectedLine = "#b45309";
    const defaultLine = "#087f5b";

    const resizeOverview = () => {
      if (overview.data) Plotly.Plots.resize(overview);
    };
    if (window.ResizeObserver) {
      new ResizeObserver(resizeOverview).observe(overview.parentElement);
    } else {
      window.addEventListener("resize", resizeOverview);
    }

    const loadDetails = () => {
      if (!detailRelations) {
        detailRelations = fetch(workspace.dataset.lineageDetails).then((response) => {
          if (!response.ok) throw new Error("Unable to load lineage detail data.");
          return response.json();
        });
      }
      return detailRelations;
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

    const overviewBounds = (figure) => {
      const shapes = figure?.layout?.shapes || [];
      if (!shapes.length) return undefined;
      return shapes.reduce((bounds, shape) => ({
        minX: Math.min(bounds.minX, Number(shape.x0)),
        maxX: Math.max(bounds.maxX, Number(shape.x1)),
        minY: Math.min(bounds.minY, Number(shape.y0)),
        maxY: Math.max(bounds.maxY, Number(shape.y1)),
      }), { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
    };

    const fitOverview = (figure) => {
      const bounds = overviewBounds(figure || activeFigure);
      const rect = overview.getBoundingClientRect();
      if (!bounds || rect.width < 20 || rect.height < 20) return;
      const padding = 44;
      let width = bounds.maxX - bounds.minX + padding * 2;
      let height = bounds.maxY - bounds.minY + padding * 2;
      const targetRatio = rect.width / rect.height;
      if (width / height < targetRatio) width = height * targetRatio;
      else height = width / targetRatio;
      const centerX = (bounds.minX + bounds.maxX) / 2;
      const centerY = (bounds.minY + bounds.maxY) / 2;
      return Plotly.relayout(overview, {
        "xaxis.autorange": false,
        "yaxis.autorange": false,
        "xaxis.range[0]": centerX - width / 2,
        "xaxis.range[1]": centerX + width / 2,
        "yaxis.range[0]": centerY + height / 2,
        "yaxis.range[1]": centerY - height / 2,
      });
    };

    const fitAfterLayout = () => new Promise((resolve) => {
      requestAnimationFrame(() => {
        resizeOverview();
        requestAnimationFrame(() => {
          Promise.resolve(fitOverview(activeFigure)).finally(resolve);
        });
      });
    });

    const centerOverview = () => {
      const bounds = overviewBounds(activeFigure);
      const xRange = overview.layout?.xaxis?.range;
      const yRange = overview.layout?.yaxis?.range;
      if (!bounds || !xRange || !yRange) return;
      const width = Math.abs(xRange[1] - xRange[0]);
      const height = Math.abs(yRange[1] - yRange[0]);
      const centerX = (bounds.minX + bounds.maxX) / 2;
      const centerY = (bounds.minY + bounds.maxY) / 2;
      return Plotly.relayout(overview, {
        "xaxis.range[0]": centerX - width / 2,
        "xaxis.range[1]": centerX + width / 2,
        "yaxis.range[0]": centerY + height / 2,
        "yaxis.range[1]": centerY - height / 2,
      });
    };

    const zoomOverview = (factor) => {
      const xRange = overview.layout?.xaxis?.range;
      const yRange = overview.layout?.yaxis?.range;
      if (!xRange || !yRange) return;
      const centerX = (xRange[0] + xRange[1]) / 2;
      const centerY = (yRange[0] + yRange[1]) / 2;
      const width = Math.abs(xRange[1] - xRange[0]) * factor;
      const height = Math.abs(yRange[1] - yRange[0]) * factor;
      return Plotly.relayout(overview, {
        "xaxis.range[0]": centerX - width / 2,
        "xaxis.range[1]": centerX + width / 2,
        "yaxis.range[0]": centerY + height / 2,
        "yaxis.range[1]": centerY - height / 2,
      });
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
      workspace.classList.remove("has-details");
      detailTitle.textContent = "选择一个插件";
      detailEmpty.hidden = false;
      detailLink.hidden = true;
      relations.hidden = true;
      inputList.replaceChildren();
      consumerList.replaceChildren();
      detailPanel.scrollTop = 0;
      detailPanel.scrollLeft = 0;
      return fitAfterLayout();
    };

    const renderRelations = (list, names, direction, emptyLabel) => {
      list.replaceChildren();
      if (!names.length) {
        const empty = document.createElement("p");
        empty.className = "relation-empty";
        empty.textContent = emptyLabel;
        list.append(empty);
        return;
      }
      for (const name of names) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "relation-link";
        button.dataset.lineageRelation = name;
        button.textContent = `${direction} ${name}`;
        button.addEventListener("click", () => {
          selectPlugin(name).then(() => updateUrl(activeView, selected));
        });
        list.append(button);
      }
    };

    const renderView = async (view) => {
      const figures = await loadOverviews();
      const figure = figures[view];
      if (!figure) throw new Error(`Unknown lineage view: ${view}`);
      activeView = view;
      activeFigure = figure;
      for (const control of viewControls) {
        const active = control.dataset.lineageView === view;
        control.classList.toggle("is-active", active);
        control.setAttribute("aria-pressed", String(active));
      }
      const overviewBounds = overview.getBoundingClientRect();
      const overviewLayout = {
        ...figure.layout,
        autosize: false,
        width: Math.max(320, Math.floor(overviewBounds.width)),
        height: Math.max(480, Math.floor(overviewBounds.height)),
        margin: { l: 18, r: 18, t: 18, b: 18 },
      };
      await Plotly.react(overview, figure.data, overviewLayout, {
        displaylogo: false, responsive: true, scrollZoom: true,
      });
      await fitAfterLayout();
    };

    const selectPlugin = async (provides) => {
      if (!provides || !overview.layout?.meta?.node_shape_indices?.[provides] && overview.layout?.meta?.node_shape_indices?.[provides] !== 0) {
        clearSelection();
        return;
      }
      selected = provides;
      highlight(provides);
      workspace.classList.add("has-details");
      detailTitle.textContent = provides;
      detailEmpty.hidden = true;
      const pluginPrefix = workspace.dataset.pluginPrefix ?? "plugins/";
      detailLink.href = `${pluginPrefix}${provides}.html`;
      detailLink.hidden = false;
      try {
        const relationMap = await loadDetails();
        if (selected !== provides) return;
        const relation = relationMap[provides] || { inputs: [], consumers: [] };
        renderRelations(inputList, relation.inputs || [], "←", "没有声明直接输入。");
        renderRelations(consumerList, relation.consumers || [], "→", "没有声明直接消费者。");
        relations.hidden = false;
        detailPanel.scrollTop = 0;
        detailPanel.scrollLeft = 0;
        await fitAfterLayout();
      } catch (error) {
        if (selected !== provides) return;
        detailEmpty.textContent = "无法加载谱系详情。";
        detailEmpty.hidden = false;
        relations.hidden = true;
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
        if (requested === "core" && terminalOutputs.has(selected)) await clearSelection();
        await renderView(requested);
        await selectPlugin(selected);
        updateUrl(activeView, selected);
      });
    }
    closeButton?.addEventListener("click", async () => {
      await clearSelection();
      updateUrl(activeView);
    });
    for (const control of document.querySelectorAll("[data-lineage-canvas]")) {
      control.addEventListener("click", async () => {
        switch (control.dataset.lineageCanvas) {
          case "zoom-in":
            await zoomOverview(0.72);
            break;
          case "zoom-out":
            await zoomOverview(1.38);
            break;
          case "fit":
            await fitOverview(activeFigure);
            break;
          case "center":
            await centerOverview();
            break;
          case "reset":
            await renderView(activeView);
            await selectPlugin(selected);
            break;
        }
      });
    }
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
