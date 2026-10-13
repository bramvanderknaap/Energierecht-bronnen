(async function () {
  const PAGE = 40;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = (iso) => new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" });

  let sources, data;
  if (window.EB_DATA) {
    ({ sources, data } = window.EB_DATA);
  } else {
    [sources, data] = await Promise.all([
      fetch("sources.json").then((r) => r.json()),
      fetch("data/items.json", { cache: "no-cache" }).then((r) => r.json()).catch(() => ({ items: [] })),
    ]);
  }
  const byId = Object.fromEntries(sources.map((s) => [s.id, s]));
  const badge = (s) => `<span class="badge ${esc(s.region.split("/")[0])}">${esc(s.region)}</span>`;

  $("updated").textContent = data.updated ? `Laatst bijgewerkt: ${fmtDate(data.updated)}` : "";

  // Tabs
  document.querySelectorAll(".tabs button").forEach((btn) =>
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b === btn));
      $("nieuw").hidden = btn.dataset.tab !== "nieuw";
      $("bronnen").hidden = btn.dataset.tab !== "bronnen";
    })
  );

  // Filters
  const withItems = sources.filter((s) => data.items.some((i) => i.source === s.id));
  let active = "alle";
  let shown = PAGE;
  $("chips").innerHTML = [`<button class="chip" data-id="alle" aria-pressed="true">Alle bronnen</button>`]
    .concat(withItems.map((s) => `<button class="chip" data-id="${esc(s.id)}" aria-pressed="false">${esc(s.name)}</button>`))
    .join("");
  $("chips").addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    active = btn.dataset.id;
    document.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === btn));
    shown = PAGE;
    render();
  });
  $("zoek").addEventListener("input", () => { shown = PAGE; render(); });
  $("more").addEventListener("click", () => { shown += PAGE; render(); });

  function render() {
    const q = $("zoek").value.trim().toLowerCase();
    const list = data.items.filter(
      (i) => (active === "alle" || i.source === active) &&
        (!q || (i.title + " " + (i.summary || "")).toLowerCase().includes(q))
    );
    $("count").textContent = `${list.length} publicatie${list.length === 1 ? "" : "s"}`;
    $("items").innerHTML = list.length
      ? list.slice(0, shown).map((i) => {
          const s = byId[i.source] || { name: i.source, region: "" };
          const when = i.date_estimated ? `gevonden op ${fmtDate(i.date)}` : fmtDate(i.date);
          return `<li>
            <a class="title" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>
            <div class="info">${badge(s)}<span>${esc(s.name)}</span><span>·</span><span>${esc(when)}</span></div>
            ${i.summary ? `<p class="summary">${esc(i.summary.length > 220 ? i.summary.slice(0, 220) + "…" : i.summary)}</p>` : ""}
          </li>`;
        }).join("")
      : `<li class="empty">Geen publicaties gevonden.</li>`;
    $("more").hidden = list.length <= shown;
  }
  render();

  // Bronnen
  $("sources").innerHTML = sources.map((s) => `
    <article class="card">
      <h2>${esc(s.name)} ${badge(s)}</h2>
      <div class="sub">${esc(s.full_name)}</div>
      <p>${esc(s.description)}</p>
      <ul>
        <li><a href="${esc(s.website)}" target="_blank" rel="noopener">Website</a></li>
        ${s.links.map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a></li>`).join("")}
      </ul>
    </article>`).join("");
})();
