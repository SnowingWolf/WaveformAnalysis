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

  const workspace = document.querySelector(".lineage-workspace[data-lineage-graph]");
  const overview = document.querySelector("#plugin-global-lineage");
  if (workspace && overview && window.cytoscape && window.ELK) {
    const detailTitle = workspace.querySelector("[data-lineage-detail-title]");
    const detailEmpty = workspace.querySelector("[data-lineage-detail-empty]");
    const detailLink = workspace.querySelector("[data-lineage-detail-link]");
    const detailPanel = workspace.querySelector(".lineage-detail");
    const relations = workspace.querySelector("[data-lineage-relations]");
    const inputList = workspace.querySelector("[data-lineage-inputs]");
    const consumerList = workspace.querySelector("[data-lineage-consumers]");
    const closeButton = workspace.querySelector("[data-lineage-detail-close]");
    const viewControls = [...document.querySelectorAll("[data-lineage-view]")];
    const tooltip = workspace.querySelector("[data-lineage-tooltip]");
    const embeddedGraph = document.querySelector("#lineage-graph-data");
    let graphPromise = embeddedGraph
      ? Promise.resolve(JSON.parse(embeddedGraph.textContent))
      : undefined;
    let selected;
    let activeView = "overview";
    let cy;
    let currentGraph;
    let fullscreenViewport;
    const elk = new ELK();

    const loadGraph = () => {
      if (!graphPromise) {
        graphPromise = fetch(workspace.dataset.lineageGraph).then((response) => {
          if (!response.ok) throw new Error("Unable to load lineage graph data.");
          return response.json();
        });
      }
      return graphPromise;
    };

    const updateUrl = (view, provides, replace = false) => {
      const url = new URL(window.location.href);
      url.searchParams.set("view", view);
      if (provides) url.searchParams.set("focus", provides);
      else url.searchParams.delete("focus");
      window.history[replace ? "replaceState" : "pushState"]({}, "", url);
    };

    const displayLabel = (name) => {
      if (name.length <= 16 || !name.includes("_")) return name;
      const breaks = [...name.matchAll(/_/g)].map((match) => match.index + 1);
      const split = breaks.reduce((best, point) => (
        Math.abs(point - name.length / 2) < Math.abs(best - name.length / 2) ? point : best
      ), breaks[0]);
      return `${name.slice(0, split)}\n${name.slice(split)}`;
    };

    const measuredNodes = (nodes) => {
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");
      context.font = "700 13px system-ui, sans-serif";
      return nodes.map((node) => {
        const label = displayLabel(node.data.label);
        const lines = label.split("\n");
        const textWidth = Math.max(...lines.map((line) => context.measureText(line).width));
        return {
          ...node,
          data: {
            ...node.data,
            displayLabel: label,
            width: Math.min(190, Math.max(110, Math.ceil(textWidth + 28))),
            height: lines.length > 1 ? 68 : 50,
          },
        };
      });
    };

    const focusNames = (graph, provides) => {
      if (!provides) return new Set();
      const incoming = new Map(graph.nodes.map((node) => [node.data.id, []]));
      const outgoing = new Map(graph.nodes.map((node) => [node.data.id, []]));
      for (const edge of graph.edges) {
        incoming.get(edge.data.target)?.push(edge.data.source);
        outgoing.get(edge.data.source)?.push(edge.data.target);
      }
      const result = new Set([provides]);
      for (const adjacency of [incoming, outgoing]) {
        let frontier = [provides];
        for (let depth = 0; depth < (graph.focusDepth || 2); depth += 1) {
          frontier = frontier.flatMap((name) => adjacency.get(name) || []);
          frontier.forEach((name) => result.add(name));
        }
      }
      return result;
    };

    const visibleNames = (graph, view) => {
      if (view === "focus") return focusNames(graph, selected);
      return new Set(graph.views[view] || graph.views.overview);
    };

    const segmentData = (source, target, bendPoints = []) => {
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const lengthSquared = dx * dx + dy * dy;
      const length = Math.sqrt(lengthSquared) || 1;
      const weights = [];
      const distances = [];
      for (const point of bendPoints) {
        weights.push(lengthSquared ? ((point.x - source.x) * dx + (point.y - source.y) * dy) / lengthSquared : 0.5);
        distances.push((dx * (point.y - source.y) - dy * (point.x - source.x)) / length);
      }
      return {
        weights: (weights.length ? weights : [0.5]).join(" "),
        distances: (distances.length ? distances : [0]).join(" "),
      };
    };

    const layoutGraph = async (nodes, edges) => {
      const measured = measuredNodes(nodes);
      const sizes = new Map(measured.map((node) => [node.data.id, node.data]));
      const elkGraph = {
        id: "root",
        layoutOptions: {
          "elk.algorithm": "layered",
          "elk.direction": "RIGHT",
          "elk.edgeRouting": "ORTHOGONAL",
          "elk.aspectRatio": "1.8",
          "elk.spacing.nodeNode": "36",
          "elk.spacing.edgeNode": "18",
          "elk.layered.spacing.nodeNodeBetweenLayers": "80",
          "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
          "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
          "elk.layered.unnecessaryBendpoints": "true",
          "elk.layered.wrapping.strategy": "MULTI_EDGE",
          "elk.layered.wrapping.correctionFactor": "1.35",
        },
        children: measured.map((node) => ({
          id: node.data.id,
          width: node.data.width,
          height: node.data.height,
          layoutOptions: { "elk.portConstraints": "FIXED_SIDE" },
          ports: [
            { id: `${node.data.id}:in`, width: 1, height: 1, layoutOptions: { "elk.port.side": "WEST" } },
            { id: `${node.data.id}:out`, width: 1, height: 1, layoutOptions: { "elk.port.side": "EAST" } },
          ],
        })),
        edges: edges.map((edge) => ({
          id: edge.data.id,
          sources: [`${edge.data.source}:out`],
          targets: [`${edge.data.target}:in`],
        })),
      };
      const result = await elk.layout(elkGraph);
      const positions = new Map(result.children.map((node) => [node.id, {
        x: node.x + node.width / 2,
        y: node.y + node.height / 2,
      }]));
      const routeById = new Map(result.edges.map((edge) => [
        edge.id,
        (edge.sections || []).flatMap((section) => [
          section.startPoint,
          ...(section.bendPoints || []),
          section.endPoint,
        ]).filter(Boolean),
      ]));
      return {
        nodes: measured.map((node) => ({ ...node, position: positions.get(node.data.id) })),
        edges: edges.map((edge) => {
          const routePoints = routeById.get(edge.data.id) || [];
          const route = segmentData(
            positions.get(edge.data.source),
            positions.get(edge.data.target),
            routePoints,
          );
          return { ...edge, data: { ...edge.data, ...route } };
        }),
        sizes,
      };
    };

    const highlight = (provides) => {
      if (!cy) return;
      cy.elements().removeClass("is-selected is-active is-inactive");
      if (!provides || !cy.getElementById(provides).length) return;
      const active = cy.getElementById(provides)
        .union(cy.getElementById(provides).predecessors())
        .union(cy.getElementById(provides).successors());
      cy.elements().not(active).addClass("is-inactive");
      active.addClass("is-active");
      cy.getElementById(provides).addClass("is-selected");
    };

    const fitGraph = () => {
      if (!cy || !cy.elements().length) return;
      cy.resize();
      cy.fit(cy.elements(), 42);
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
          selectPlugin(name, { updateHistory: true });
        });
        list.append(button);
      }
    };

    const renderView = async (view) => {
      const graph = currentGraph || await loadGraph();
      currentGraph = graph;
      const names = visibleNames(graph, view);
      if (view === "focus" && !names.size) return;
      const nodes = graph.nodes.filter((node) => names.has(node.data.id));
      const edges = graph.edges.filter((edge) => names.has(edge.data.source) && names.has(edge.data.target));
      const laidOut = await layoutGraph(nodes, edges);
      activeView = view;
      for (const control of viewControls) {
        const active = control.dataset.lineageView === view;
        control.classList.toggle("is-active", active);
        control.setAttribute("aria-pressed", String(active));
      }
      if (cy) cy.destroy();
      cy = cytoscape({
        container: overview,
        elements: [...laidOut.edges, ...laidOut.nodes],
        layout: { name: "preset", fit: false },
        minZoom: 0.15,
        maxZoom: 3.5,
        wheelSensitivity: 0.18,
        style: [
          { selector: "node", style: { "width": "data(width)", "height": "data(height)", "shape": "roundrectangle", "background-color": "#ffffff", "border-color": "#087f5b", "border-width": 1.5, "label": "data(displayLabel)", "font-size": 13, "font-weight": 700, "font-family": "system-ui, sans-serif", "color": "#17201d", "text-wrap": "wrap", "text-valign": "center", "text-halign": "center", "padding": 0, "overlay-opacity": 0 } },
          { selector: "node[kind = 'input']", style: { "border-color": "#64748b" } },
          { selector: "node[kind = 'waveform']", style: { "border-color": "#2563eb" } },
          { selector: "node[kind = 'hit']", style: { "border-color": "#7e22ce" } },
          { selector: "node[kind = 'peaklet']", style: { "border-color": "#15803d" } },
          { selector: "node[kind = 'output']", style: { "border-color": "#b45309", "border-width": 2 } },
          { selector: "edge", style: { "curve-style": "segments", "segment-weights": "data(weights)", "segment-distances": "data(distances)", "line-color": "#8296a5", "target-arrow-color": "#8296a5", "target-arrow-shape": "triangle", "arrow-scale": 0.7, "width": 1.2, "line-cap": "round", "overlay-opacity": 0 } },
          { selector: "edge[kind = 'main']", style: { "line-color": "#456a80", "target-arrow-color": "#456a80", "width": 2.4, "arrow-scale": 0.85 } },
          { selector: "edge[kind = 'auxiliary']", style: { "line-color": "#b8c2c9", "target-arrow-color": "#b8c2c9", "line-style": "dashed", "width": 1 } },
          { selector: ".is-inactive", style: { "opacity": 0.1 } },
          { selector: ".is-active", style: { "opacity": 1 } },
          { selector: "node.is-selected", style: { "background-color": "#fff1d8", "border-color": "#b45309", "border-width": 3 } },
        ],
      });
      overview._lineageCy = cy;
      overview._lineageLayout = laidOut;
      overview.dataset.lineageReady = "true";
      overview.dataset.lineageNodeCount = String(laidOut.nodes.length);
      cy.on("tap", "node", (event) => selectPlugin(event.target.id(), { updateHistory: true }));
      cy.on("dbltap", "node", (event) => { window.location.href = event.target.data("href"); });
      cy.on("mouseover", "node", (event) => {
        const node = event.target;
        tooltip.textContent = `${node.id()} · ${node.data("pluginClass")} · Docs ${node.data("documentationCompleteness")}/100 · Impact ${node.data("dagImpact")}/100`;
        tooltip.hidden = false;
      });
      cy.on("mousemove", "node", (event) => {
        tooltip.style.left = `${event.renderedPosition.x + 14}px`;
        tooltip.style.top = `${event.renderedPosition.y + 14}px`;
      });
      cy.on("mouseout", "node", () => { tooltip.hidden = true; });
      highlight(selected);
      requestAnimationFrame(fitGraph);
    };

    const selectPlugin = async (provides, { updateHistory = false } = {}) => {
      const graph = currentGraph || await loadGraph();
      if (!provides || !graph.nodes.some((node) => node.data.id === provides)) return;
      selected = provides;
      document.querySelector('[data-lineage-view="focus"]')?.removeAttribute("disabled");
      workspace.classList.add("has-details");
      detailTitle.textContent = provides;
      detailEmpty.hidden = true;
      const pluginPrefix = workspace.dataset.pluginPrefix ?? "plugins/";
      detailLink.href = `${pluginPrefix}${provides}.html`;
      detailLink.hidden = false;
      const relation = graph.relations[provides] || { inputs: [], consumers: [] };
      renderRelations(inputList, relation.inputs || [], "←", "没有声明直接输入。");
      renderRelations(consumerList, relation.consumers || [], "→", "没有声明直接消费者。");
      relations.hidden = false;
      detailPanel.scrollTop = 0;
      detailPanel.scrollLeft = 0;
      if (activeView === "focus") await renderView("focus");
      else highlight(provides);
      if (updateHistory) updateUrl(activeView, selected);
    };

    const clearSelection = async () => {
      selected = undefined;
      highlight();
      workspace.classList.remove("has-details");
      detailTitle.textContent = "选择一个插件";
      detailEmpty.hidden = false;
      detailLink.hidden = true;
      relations.hidden = true;
      inputList.replaceChildren();
      consumerList.replaceChildren();
      if (activeView === "focus") await renderView("overview");
      else requestAnimationFrame(fitGraph);
    };

    const restoreState = async ({ replace = false } = {}) => {
      const params = new URLSearchParams(window.location.search);
      const requested = params.get("view");
      let view = ["full", "focus"].includes(requested) ? requested : "overview";
      const focus = params.get("focus");
      currentGraph = await loadGraph();
      if (focus) selected = focus;
      if (view === "focus" && !focus) view = "overview";
      await renderView(view);
      if (focus) await selectPlugin(focus);
      if (replace) updateUrl(view, selected, true);
    };

    for (const control of viewControls) {
      control.addEventListener("click", async () => {
        const requested = control.dataset.lineageView;
        if (requested === activeView || (requested === "focus" && !selected)) return;
        await renderView(requested);
        updateUrl(activeView, selected);
      });
    }
    closeButton?.addEventListener("click", async () => {
      await clearSelection();
      updateUrl(activeView);
    });
    const detailToggle = document.querySelector("[data-lineage-detail-toggle]");
    const setDetailCollapsed = async (collapsed) => {
      workspace.dataset.detailCollapsed = String(collapsed);
      detailToggle?.setAttribute("aria-expanded", String(!collapsed));
      if (detailToggle) {
        detailToggle.title = collapsed ? "展开节点详情" : "折叠节点详情";
        detailToggle.setAttribute("aria-label", detailToggle.title);
        detailToggle.textContent = collapsed ? "◀" : "▶";
      }
      requestAnimationFrame(fitGraph);
    };
    detailToggle?.addEventListener("click", () => setDetailCollapsed(workspace.dataset.detailCollapsed !== "true"));

    const fullscreenButton = document.querySelector("[data-lineage-fullscreen]");
    const syncFullscreen = async () => {
      const fullscreen = document.fullscreenElement === workspace;
      if (fullscreen) fullscreenViewport = cy ? { zoom: cy.zoom(), pan: cy.pan() } : undefined;
      workspace.dataset.fullscreen = String(fullscreen);
      fullscreenButton?.setAttribute("aria-pressed", String(fullscreen));
      if (fullscreenButton) {
        fullscreenButton.title = fullscreen ? "退出全屏" : "全屏查看图谱";
        fullscreenButton.setAttribute("aria-label", fullscreenButton.title);
      }
      requestAnimationFrame(() => {
        cy?.resize();
        if (fullscreen) fitGraph();
        else if (fullscreenViewport && cy) cy.viewport(fullscreenViewport);
      });
    };
    fullscreenButton?.addEventListener("click", async () => {
      if (document.fullscreenElement === workspace) await document.exitFullscreen();
      else await workspace.requestFullscreen?.();
    });
    document.addEventListener("fullscreenchange", syncFullscreen);
    for (const control of document.querySelectorAll("[data-lineage-canvas]")) {
      control.addEventListener("click", async () => {
        switch (control.dataset.lineageCanvas) {
          case "zoom-in":
            cy?.zoom({ level: Math.min(3.5, cy.zoom() * 1.2), renderedPosition: { x: overview.clientWidth / 2, y: overview.clientHeight / 2 } });
            break;
          case "zoom-out":
            cy?.zoom({ level: Math.max(0.15, cy.zoom() / 1.2), renderedPosition: { x: overview.clientWidth / 2, y: overview.clientHeight / 2 } });
            break;
          case "fit":
            fitGraph();
            break;
          case "center":
            cy?.center();
            break;
          case "reset":
            await renderView(activeView);
            break;
        }
      });
    }
    if (window.ResizeObserver) {
      new ResizeObserver(() => cy?.resize()).observe(overview.parentElement);
    } else {
      window.addEventListener("resize", () => cy?.resize());
    }
    window.addEventListener("popstate", () => restoreState());
    restoreState({ replace: true }).catch((error) => {
      console.error("Unable to render plugin DAG", error);
      overview.textContent = "插件 DAG 加载失败。";
    });
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

  const readStorage = (key) => {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  };
  const writeStorage = (key, value) => {
    try { localStorage.setItem(key, value); } catch (_) {}
  };
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
  const layout = nav?.parentElement;
  const navRestore = document.querySelector("[data-doc-nav-restore]");
  const setNavigationVisibility = (hidden) => {
    if (!layout || !navOpen) return;
    layout.classList.toggle("is-navigation-hidden", hidden);
    document.body.classList.toggle("is-navigation-hidden", hidden);
    const label = hidden ? "显示文档导航" : "打开文档导航";
    navOpen.title = label;
    navOpen.setAttribute("aria-label", label);
    navOpen.querySelector("span:last-child").textContent = hidden ? "显示目录" : "目录";
  };
  const visibilityToggle = nav?.querySelector("[data-tree-visibility-toggle]");
  const restoreNavigation = () => {
    setNavigationVisibility(false);
    visibilityToggle?.setAttribute("aria-pressed", "false");
    if (visibilityToggle) {
      visibilityToggle.title = "隐藏文档导航";
      visibilityToggle.querySelector(".sr-only").textContent = visibilityToggle.title;
    }
    writeStorage("waveform-docs-navigation-hidden", "false");
  };
  if (layout && visibilityToggle) {
    const storageKey = "waveform-docs-navigation-hidden";
    const setVisibilityToggle = (hidden) => {
      visibilityToggle.setAttribute("aria-pressed", String(hidden));
      const label = hidden ? "显示文档导航" : "隐藏文档导航";
      visibilityToggle.title = label;
      visibilityToggle.querySelector(".sr-only").textContent = label;
    };
    const hidden = readStorage("waveform-docs-navigation-hidden") === "true";
    setNavigationVisibility(hidden);
    setVisibilityToggle(hidden);
    visibilityToggle.addEventListener("click", () => {
      const nextHidden = !layout.classList.contains("is-navigation-hidden");
      setNavigationVisibility(nextHidden);
      setVisibilityToggle(nextHidden);
      writeStorage(storageKey, String(nextHidden));
    });
  }
  navOpen?.addEventListener("click", () => {
    if (layout?.classList.contains("is-navigation-hidden")) {
      restoreNavigation();
    } else {
      setNavigation(true);
    }
  });
  navRestore?.addEventListener("click", restoreNavigation);
  navClose?.addEventListener("click", () => setNavigation(false));
  for (const toggle of document.querySelectorAll("[data-tree-toggle]")) {
    const target = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!target) continue;
    const storageKey = `waveform-docs-tree:${target.id}`;
    const containsCurrentPage = Boolean(target.querySelector('[aria-current="page"]'));
    const stored = readStorage(storageKey);
    const expanded = containsCurrentPage || stored !== "false";
    toggle.setAttribute("aria-expanded", String(expanded));
    target.hidden = !expanded;
    const setTitle = (nextExpanded) => {
      const label = toggle.closest(".site-tree-group")?.querySelector(".site-tree-group-row")?.textContent?.trim() || "分组";
      const action = nextExpanded ? "折叠" : "展开";
      toggle.title = `${action} ${label}`;
      toggle.querySelector(".sr-only").textContent = `${action} ${label}`;
    };
    setTitle(expanded);
    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(expanded));
      target.hidden = !expanded;
      writeStorage(storageKey, String(expanded));
      setTitle(expanded);
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
    if (document.querySelector("[data-mermaid-block]")) window.location.reload();
  });

  const mermaidBlocks = [...document.querySelectorAll("[data-mermaid-block]")];
  if (mermaidBlocks.length) {
    if (!window.mermaid) {
      for (const block of mermaidBlocks) block.querySelector("[data-mermaid-error]").hidden = false;
    } else {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        suppressErrorRendering: true,
        theme: document.documentElement.dataset.theme === "dark" ? "dark" : "default",
      });
      mermaidBlocks.forEach(async (block, index) => {
        const source = block.querySelector(".mermaid-source");
        const target = block.querySelector("[data-mermaid-render]");
        const error = block.querySelector("[data-mermaid-error]");
        try {
          const result = await window.mermaid.render(
            `waveform-mermaid-${index}`,
            source.textContent,
          );
          target.innerHTML = result.svg;
          result.bindFunctions?.(target);
          source.hidden = true;
          block.classList.add("is-rendered");
        } catch (renderError) {
          error.hidden = false;
          console.error("Unable to render Mermaid diagram", renderError);
        }
      });
    }
  }

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
  const tocToggle = toc?.querySelector("[data-page-toc-toggle]");
  const tocPin = toc?.querySelector("[data-page-toc-pin]");
  const tocExpandAll = toc?.querySelector("[data-page-toc-expand-all]");
  const tocCollapseAll = toc?.querySelector("[data-page-toc-collapse-all]");
  const slugify = (value, fallback) => {
    const normalized = value.toLocaleLowerCase().trim().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-").replace(/^-+|-+$/g, "");
    return normalized || fallback;
  };
  const tocTargets = [];
  const tocGroups = [];
  const setTocOpen = (open) => {
    if (!toc || !tocToggle) return;
    toc.classList.toggle("is-open", open);
    tocToggle.setAttribute("aria-expanded", String(open));
    tocToggle.title = open ? "收起本页目录" : "显示本页目录";
    tocToggle.querySelector(".sr-only").textContent = tocToggle.title;
  };
  const setTocPinned = (pinned) => {
    if (!toc || !tocPin) return;
    toc.classList.toggle("is-pinned", pinned);
    tocPin.setAttribute("aria-pressed", String(pinned));
    tocPin.title = pinned ? "取消固定目录" : "固定目录";
    tocPin.querySelector(".sr-only").textContent = tocPin.title;
    if (pinned) setTocOpen(true);
  };
  const setGroupExpanded = (group, expanded) => {
    if (!group) return;
    group.list.hidden = !expanded;
    group.toggle.setAttribute("aria-expanded", String(expanded));
    group.toggle.title = expanded ? `折叠 ${group.title}` : `展开 ${group.title}`;
    group.toggle.querySelector(".sr-only").textContent = group.toggle.title;
  };
  if (tocList) {
    const usedIds = new Set([...document.querySelectorAll("[id]")].map((element) => element.id));
    let currentGroup;
    const headings = [...document.querySelectorAll(".docs-main h2, .docs-main h3, .docs-main h4")]
      .filter((heading) => !heading.closest(".resource-card, .lineage-section, .page-heading"));
    for (const heading of headings) {
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
      const link = document.createElement("a");
      link.href = `#${target.id}`;
      link.dataset.tocLevel = heading.tagName.slice(1);
      link.textContent = heading.textContent.trim();
      link.addEventListener("click", (event) => {
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", `#${target.id}`);
      });
      if (heading.tagName === "H2") {
        const item = document.createElement("li");
        item.className = "page-toc-group";
        const row = document.createElement("div");
        row.className = "page-toc-group-row";
        const groupToggle = document.createElement("button");
        groupToggle.type = "button";
        groupToggle.className = "page-toc-group-toggle";
        const groupId = `page-toc-group-${tocGroups.length + 1}`;
        groupToggle.setAttribute("aria-controls", groupId);
        groupToggle.innerHTML = '<span aria-hidden="true"></span><span class="sr-only"></span>';
        row.append(groupToggle, link);
        const children = document.createElement("ol");
        children.id = groupId;
        item.append(row, children);
        tocList.append(item);
        const group = { title: link.textContent, list: children, toggle: groupToggle, item };
        currentGroup = group;
        tocGroups.push(group);
        setGroupExpanded(group, tocGroups.length === 1);
        groupToggle.addEventListener("click", () => {
          setGroupExpanded(group, groupToggle.getAttribute("aria-expanded") !== "true");
        });
      } else if (currentGroup) {
        const item = document.createElement("li");
        item.className = "page-toc-item";
        item.append(link);
        currentGroup.list.append(item);
      } else {
        const item = document.createElement("li");
        item.className = "page-toc-item";
        item.append(link);
        tocList.append(item);
      }
      tocTargets.push([target, link, currentGroup]);
    }
  }
  if (!tocTargets.length) {
    if (toc) toc.hidden = true;
  } else if (toc) {
    setTocOpen(false);
    setTocPinned(false);
    toc.addEventListener("mouseenter", () => setTocOpen(true));
    toc.addEventListener("mouseleave", () => {
      if (!toc.classList.contains("is-pinned")) setTocOpen(false);
    });
    toc.addEventListener("focusin", () => setTocOpen(true));
    toc.addEventListener("focusout", () => {
      window.setTimeout(() => {
        if (!toc.contains(document.activeElement) && !toc.classList.contains("is-pinned")) setTocOpen(false);
      }, 0);
    });
    tocToggle?.addEventListener("click", () => {
      setTocPinned(!toc.classList.contains("is-pinned"));
      if (!toc.classList.contains("is-pinned")) setTocOpen(false);
    });
    tocPin?.addEventListener("click", () => setTocPinned(!toc.classList.contains("is-pinned")));
    tocExpandAll?.addEventListener("click", () => {
      for (const group of tocGroups) setGroupExpanded(group, true);
    });
    tocCollapseAll?.addEventListener("click", () => {
      for (const group of tocGroups) setGroupExpanded(group, false);
    });
  }
  if (tocTargets.length && window.IntersectionObserver) {
    const tocLinks = tocTargets.map(([, link]) => link);
    const byId = new Map(tocTargets.map(([target, link, group]) => [target.id, { link, group }]));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      const activeEntry = byId.get(visible.target.id);
      for (const link of tocLinks) {
        const active = link === activeEntry?.link;
        link.classList.toggle("is-active", active);
        if (active) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
      if (activeEntry?.group) {
        for (const group of tocGroups) setGroupExpanded(group, group === activeEntry.group);
      }
    }, { rootMargin: "-80px 0px -65% 0px" });
    for (const [target] of tocTargets) observer.observe(target);
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && toc?.classList.contains("is-open") && !toc.classList.contains("is-pinned")) {
      setTocOpen(false);
      tocToggle?.blur();
    }
  });
})();
