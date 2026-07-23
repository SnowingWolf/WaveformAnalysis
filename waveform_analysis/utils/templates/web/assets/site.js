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
      status.textContent = `${visible} plugin${visible === 1 ? "" : "s"}`;
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
    let detailFigures;
    let selected;
    const selectedLine = "#b45309";
    const defaultLine = "#087f5b";

    const loadDetails = () => {
      if (!detailFigures) {
        detailFigures = fetch(workspace.dataset.lineageDetails).then((response) => {
          if (!response.ok) throw new Error("Unable to load lineage detail data.");
          return response.json();
        });
      }
      return detailFigures;
    };

    const updateUrl = (provides) => {
      const url = new URL(window.location.href);
      if (provides) url.searchParams.set("focus", provides);
      else url.searchParams.delete("focus");
      window.history.pushState({}, "", url);
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
      detailTitle.textContent = "Select a plugin";
      detailEmpty.hidden = false;
      detailLink.hidden = true;
      detailPlot.hidden = true;
      detailPlot.replaceChildren();
    };

    const selectPlugin = async (provides, pushUrl = false) => {
      if (!provides || !overview.layout?.meta?.node_shape_indices?.[provides] && overview.layout?.meta?.node_shape_indices?.[provides] !== 0) {
        clearSelection();
        return;
      }
      selected = provides;
      highlight(provides);
      detailTitle.textContent = provides;
      detailEmpty.hidden = true;
      detailLink.href = `plugins/${provides}.html`;
      detailLink.hidden = false;
      detailPlot.hidden = false;
      if (pushUrl) updateUrl(provides);
      try {
        const figures = await loadDetails();
        if (selected !== provides) return;
        const figure = figures[provides];
        if (!figure) throw new Error("Lineage detail is unavailable.");
        Plotly.react(detailPlot, figure.data, figure.layout, {
          displaylogo: false,
          responsive: true,
          scrollZoom: true,
        });
      } catch (error) {
        if (selected !== provides) return;
        detailEmpty.textContent = "Lineage detail could not be loaded.";
        detailEmpty.hidden = false;
        detailPlot.hidden = true;
      }
    };

    overview.on("plotly_click", (event) => {
      const provides = event.points[0]?.customdata;
      if (provides) selectPlugin(provides, true);
    });
    closeButton?.addEventListener("click", () => {
      clearSelection();
      updateUrl();
    });
    window.addEventListener("popstate", () => {
      selectPlugin(new URLSearchParams(window.location.search).get("focus"));
    });
    selectPlugin(new URLSearchParams(window.location.search).get("focus"));
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
