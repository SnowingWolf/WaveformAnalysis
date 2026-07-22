(() => {
  const input = document.querySelector("#plugin-search");
  const cards = [...document.querySelectorAll(".plugin-card")];
  const status = document.querySelector("#search-status");
  if (!input || !status) return;
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
})();
