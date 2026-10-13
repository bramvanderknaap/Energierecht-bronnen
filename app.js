(async function () {
  const PAGE = 40;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = (iso) => new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });

  let sources, data, tags;
  if (window.EB_DATA) {
    ({ sources, data, tags } = window.EB_DATA);
  } else {
    [sources, data, tags] = await Promise.all([
      fetch("sources.json").then((r) => r.json()),
      fetch("data/items.json", { cache: "no-cache" }).then((r) => r.json()).catch(() => ({ items: [] })),
      fetch("tags.json").then((r) => r.json()).catch(() => ({ groups: [] })),
    ]);
  }
  const byId = Object.fromEntries(sources.map((s) => [s.id, s]));
  const badge = (s) => `<span class="badge ${esc(s.region.split("/")[0])}">${esc(s.region)}</span>`;

  $("updated").textContent = data.updated ? `Bijgewerkt op ${new Date(data.updated).toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" })}` : "";

  // Tabs
  document.querySelectorAll(".tabs button").forEach((btn) =>
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b === btn));
      $("nieuw").hidden = btn.dataset.tab !== "nieuw";
      $("bronnen").hidden = btn.dataset.tab !== "bronnen";
    })
  );

  // Labels: een artikel krijgt een label als een trefwoord als heel woord in titel of samenvatting staat.
  const OVERIG = "overig";
  const toRegex = (kw) => {
    const open = kw.endsWith("*");
    const word = kw.replace(/\*$/, "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(^|[^\\p{L}\\p{N}])${word}${open ? "" : "(?![\\p{L}\\p{N}])"}`, "iu");
  };
  const groups = tags.groups.map((g) => ({
    ...g,
    tags: g.tags.map((t) => ({ ...t, patterns: t.keywords.map(toRegex) })),
  }));
  data.items.forEach((item) => {
    const text = `${item.title} ${item.summary || ""}`;
    item.tags = {};
    groups.forEach((g) => {
      const found = g.tags.filter((t) => (t.sources || []).includes(item.source) || t.patterns.some((p) => p.test(text))).map((t) => t.id);
      item.tags[g.id] = found.length ? found : [OVERIG];
    });
  });
  const tagLabel = Object.fromEntries(groups.flatMap((g) => g.tags.map((t) => [t.id, t.label])));

  // Filters: bron plus één keuze per labelgroep.
  const filters = [
    {
      id: "bron",
      label: "Bron",
      options: sources.filter((s) => data.items.some((i) => i.source === s.id)).map((s) => ({ id: s.id, label: s.name })),
      match: (item, value) => item.source === value,
    },
    ...groups.map((g) => ({
      id: g.id,
      label: g.label,
      options: g.tags
        .map((t) => ({ id: t.id, label: t.label, count: data.items.filter((i) => i.tags[g.id].includes(t.id)).length }))
        .filter((o) => o.count)
        .concat([{ id: OVERIG, label: "Overig", count: data.items.filter((i) => i.tags[g.id].includes(OVERIG)).length }])
        .filter((o) => o.count),
      match: (item, value) => item.tags[g.id].includes(value),
    })),
  ];
  const active = Object.fromEntries(filters.map((f) => [f.id, "alle"]));
  let shown = PAGE;

  $("chips").innerHTML = filters.map((f) => `
    <div class="filter" data-filter="${esc(f.id)}">
      <span class="filter-label">${esc(f.label)}</span>
      <div class="chip-row">
        <button class="chip" data-id="alle" aria-pressed="true">Alle</button>
        ${f.options.map((o) => `<button class="chip" data-id="${esc(o.id)}" aria-pressed="false">${esc(o.label)}</button>`).join("")}
      </div>
    </div>`).join("");
  $("chips").addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    const row = btn.closest(".filter");
    active[row.dataset.filter] = btn.dataset.id;
    row.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === btn));
    shown = PAGE;
    render();
  });
  $("zoek").addEventListener("input", () => { shown = PAGE; render(); });
  $("more").addEventListener("click", () => { shown += PAGE; render(); });

  function render() {
    const q = $("zoek").value.trim().toLowerCase();
    const list = data.items.filter(
      (i) => filters.every((f) => active[f.id] === "alle" || f.match(i, active[f.id])) &&
        (!q || (i.title + " " + (i.summary || "")).toLowerCase().includes(q))
    );
    $("count").textContent = `${list.length} publicatie${list.length === 1 ? "" : "s"}`;
    $("items").innerHTML = list.length
      ? list.slice(0, shown).map((i) => {
          const s = byId[i.source] || { name: i.source, region: "" };
          const when = i.date_estimated ? `gevonden ${fmtDate(i.date)}` : fmtDate(i.date);
          const labels = Object.values(i.tags).flat().filter((t) => t !== OVERIG);
          return `<li>
            <div class="date">${esc(when)}</div>
            <div class="body">
              <a class="title" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>
              <div class="info">${badge(s)}<span>${esc(s.full_name || s.name)}</span></div>
              ${i.summary ? `<p class="summary">${esc(i.summary.length > 220 ? i.summary.slice(0, 220) + "…" : i.summary)}</p>` : ""}
              ${labels.length ? `<div class="tags">${labels.map((t) => `<span class="tag">${esc(tagLabel[t])}</span>`).join("")}</div>` : ""}
            </div>
          </li>`;
        }).join("")
      : `<li class="empty">Geen publicaties gevonden. Kies bij een filter "Alle" om meer te zien.</li>`;
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
