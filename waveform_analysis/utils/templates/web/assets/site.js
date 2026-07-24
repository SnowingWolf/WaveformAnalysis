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
})();
