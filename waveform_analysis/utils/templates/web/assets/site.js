(() => {
  const input = document.querySelector("#plugin-search");
  const cards = [...document.querySelectorAll(".plugin-card")];
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
      status.textContent = `${visible} plugin${visible === 1 ? "" : "s"}`;
    };
    input.addEventListener("input", update);
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
