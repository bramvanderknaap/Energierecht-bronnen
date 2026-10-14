(async function () {
  "use strict";
  const PAGE = 40;
  const TZ = "Europe/Amsterdam";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

  // Datums: alles in Nederlandse tijd, dagen als "JJJJ-MM-DD"
  const dayKey = (iso) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
  const fmt = (iso, opts) => new Date(iso).toLocaleDateString("nl-NL", { timeZone: TZ, ...opts });
  const keyToUTC = (k) => Date.UTC(+k.slice(0, 4), +k.slice(5, 7) - 1, +k.slice(8, 10));
  const daysBetween = (a, b) => Math.round((keyToUTC(a) - keyToUTC(b)) / 86400000);
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  // ---------- Landschap (decoratief, uit assets/) ----------
  const land = $("land");
  const mqNarrow = matchMedia("(max-width: 719.98px)");
  async function loadLand() {
    const url = mqNarrow.matches ? "assets/landschap-smal.svg" : "assets/landschap-breed.svg";
    if (land.dataset.src === url) return;
    land.dataset.src = url;
    try {
      const svg = await (await fetch(url)).text();
      if (land.dataset.src === url) land.innerHTML = svg;
    } catch (e) { /* zonder tekening werkt de site gewoon */ }
  }
  loadLand();
  mqNarrow.addEventListener?.("change", loadLand);

  // ---------- Gegevens ----------
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
  const items = data.items
    .map((i) => ({ ...i, day: dayKey(i.date) }))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  const today = dayKey(data.updated || new Date().toISOString());
  items.forEach((i) => { i.age = daysBetween(today, i.day); });

  if (data.updated) {
    $("updated").textContent = `Laatst bijgewerkt op ${fmt(data.updated, { day: "numeric", month: "long", year: "numeric" })}`;
  }

  // Bronnen met publicaties, in de volgorde van sources.json
  const feedSources = sources.filter((s) => items.some((i) => i.source === s.id));
  const countBy = Object.fromEntries(feedSources.map((s) => [s.id, items.filter((i) => i.source === s.id).length]));

  // ---------- Filters ----------
  const state = { bron: "alle", periode: "alles", nl: false, q: "", shown: PAGE };

  $("bronList").innerHTML = [`<li><label class="check"><input type="radio" name="bron" value="alle" checked><span>Alle bronnen</span><span class="n">${items.length}</span></label></li>`]
    .concat(feedSources.map((s) => `<li><label class="check"><input type="radio" name="bron" value="${esc(s.id)}"><span>${esc(s.name)}</span><span class="n">${countBy[s.id]}</span></label></li>`))
    .join("");

  // Onderwerpen: zoeken op Nederlandse en Engelse varianten tegelijk
  const TOPICS = [
    { label: "Netcongestie", terms: ["congestie", "congestion", "transportcapaciteit", "netcapaciteit", "grid capacity"] },
    { label: "Aansluiten", terms: ["aansluit", "connection"] },
    { label: "Tarieven", terms: ["tarie", "tariff"] },
    { label: "Warmte", terms: ["warmte", "heat"] },
    { label: "Waterstof", terms: ["waterstof", "hydrogen"] },
    { label: "Flexibiliteit", terms: ["flexib", "demand response", "vraagrespons"] },
    { label: "Netcodes", terms: ["netcode", "network code", "codebesluit"] },
    { label: "Methaan", terms: ["methaan", "methane"] },
    { label: "Consumenten", terms: ["consument", "consumer", "huishouden", "household"] },
  ];
  const textOf = (i) => `${i.title} ${i.summary || ""}`.toLowerCase();
  const topicFor = (q) => TOPICS.find((t) => t.label.toLowerCase() === q.toLowerCase());
  const matchesQ = (i, q) => {
    if (!q) return true;
    const t = topicFor(q);
    const text = textOf(i);
    return t ? t.terms.some((w) => text.includes(w)) : text.includes(q.toLowerCase());
  };
  const liveTopics = TOPICS.filter((t) => items.some((i) => matchesQ(i, t.label)));
  if (liveTopics.length) {
    $("topics").innerHTML = liveTopics.map((t) => `<button class="chip" type="button" aria-pressed="false" data-q="${esc(t.label)}">${esc(t.label)}</button>`).join("");
    $("topicGroup").hidden = false;
  }

  // Geldt het voor Nederland? Nederlandse bronnen altijd; Europese berichten tenzij ze over een ander land gaan.
  const woorden = (lijst) => new RegExp(
    `(^|[^\\p{L}\\p{N}])(${lijst.map((w) => w.replace("*", "\\p{L}*")).join("|")})(?![\\p{L}\\p{N}])`, "iu");
  const NEDERLAND = woorden(["netherlands", "dutch", "nederland*"]);
  const ANDER_LAND = woorden([
    "austria*", "oostenrijk*", "belgi*", "bulgaria*", "bulgarije", "croatia*", "kroatië", "cyprus", "cypriot",
    "czech*", "tsjechië", "denmark", "danish", "denemarken", "estonia*", "finland", "finnish", "france", "french", "frankrijk",
    "german*", "duitsland", "greece", "greek", "griekenland", "hungar*", "hongarije", "ireland", "irish", "ierland",
    "italy", "italian", "italië", "latvia*", "letland", "lithuania*", "litouwen", "luxembourg*", "malta", "maltese", "poland", "polen",
    "portug*", "romania*", "roemenië", "slovak*", "slowakije", "slovenia*", "slovenië", "spain", "spanish", "spanje",
    "sweden", "swedish", "zweden", "norway", "norwegian", "noorwegen", "armenia*", "georgia*", "ukrain*", "oekraïne", "moldova*",
    "türkiye", "turkey", "turkije", "azerbaijan*", "caucasus", "balkan*", "albania*", "serbia*", "montenegr*",
  ]);
  const geldtVoorNL = (item) => {
    const s = byId[item.source];
    if (s && s.region === "NL") return true;
    const text = `${item.title} ${item.summary || ""}`;
    return NEDERLAND.test(text) || !ANDER_LAND.test(text);
  };

  const form = $("filterForm");
  const zoek = $("zoek");

  function filtered() {
    const maxAge = state.periode === "alles" ? Infinity : +state.periode;
    return items.filter((i) =>
      i.age < maxAge &&
      (state.bron === "alle" || i.source === state.bron) &&
      (!state.nl || geldtVoorNL(i)) &&
      matchesQ(i, state.q));
  }

  function itemHtml(i) {
    const s = byId[i.source] || { name: i.source, region: "" };
    const summary = i.summary ? (i.summary.length > 240 ? i.summary.slice(0, 240).trimEnd() + "…" : i.summary) : "";
    const est = i.date_estimated ? " · datum geschat" : "";
    return `<li class="item">
      <p class="src"><b>${esc(s.name)}</b>${s.region ? ` · ${esc(s.region)}` : ""}${est}</p>
      <h4><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a></h4>
      ${summary ? `<p class="sum">${esc(summary)}</p>` : ""}
    </li>`;
  }

  function render() {
    const list = filtered();
    const visible = list.slice(0, state.shown);
    const days = [];
    visible.forEach((i) => {
      const last = days[days.length - 1];
      if (last && last.day === i.day) last.items.push(i);
      else days.push({ day: i.day, items: [i] });
    });
    $("tl").innerHTML = days.map((d) => {
      const date = cap(fmt(`${d.day}T12:00:00Z`, { weekday: "long", day: "numeric", month: "long", year: "numeric" }));
      return `<section class="day"><h3><time datetime="${d.day}">${esc(date)}</time></h3><ol class="items">${d.items.map(itemHtml).join("")}</ol></section>`;
    }).join("");
    const s = byId[state.bron];
    $("count").textContent = `${list.length} publicatie${list.length === 1 ? "" : "s"}`;
    $("empty").hidden = list.length > 0;
    $("more").hidden = list.length <= state.shown;
    const parts = [state.periode === "alles" ? "" : `${state.periode} dagen`, s ? s.name : "", state.q && topicFor(state.q) ? state.q : "", state.nl ? "NL" : ""].filter(Boolean);
    $("fState").textContent = parts.join(" · ");
    document.querySelectorAll("#topics .chip").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.q.toLowerCase() === state.q.toLowerCase())));
  }

  form.addEventListener("change", (e) => {
    if (e.target.name === "periode") state.periode = e.target.value;
    if (e.target.name === "bron") state.bron = e.target.value;
    if (e.target.id === "alleenNL") state.nl = e.target.checked;
    state.shown = PAGE;
    render();
  });
  zoek.addEventListener("input", () => { state.q = zoek.value.trim(); state.shown = PAGE; render(); });
  $("searchForm").addEventListener("submit", (e) => { e.preventDefault(); state.q = zoek.value.trim(); render(); goList(); });
  $("topics").addEventListener("click", (e) => {
    const c = e.target.closest(".chip");
    if (!c) return;
    state.q = state.q.toLowerCase() === c.dataset.q.toLowerCase() ? "" : c.dataset.q;
    zoek.value = state.q;
    state.shown = PAGE;
    render();
  });
  $("more").addEventListener("click", () => { state.shown += PAGE; render(); });
  $("resetBtn").addEventListener("click", () => {
    form.reset();
    Object.assign(state, { bron: "alle", periode: "alles", nl: false, q: "", shown: PAGE });
    zoek.value = "";
    render();
  });

  function goList() {
    const t = $("tijdlijn");
    t.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "start" });
    t.focus({ preventScroll: true });
  }

  // Filters: open op desktop, inklapbaar op kleine schermen
  const det = $("filters");
  const mqDesk = matchMedia("(min-width: 901px)");
  const syncDet = () => { det.open = mqDesk.matches; };
  syncDet();
  mqDesk.addEventListener?.("change", syncDet);
  det.querySelector("summary").addEventListener("click", (e) => { if (mqDesk.matches) e.preventDefault(); });

  render();

  // ---------- Bronnen ----------
  $("sources").innerHTML = sources.map((s) => `<article class="card">
      <div class="card-head"><h3>${esc(s.name)}</h3><span class="badge">${esc(s.region)}</span></div>
      <p class="sub">${esc(s.full_name)}</p>
      <p>${esc(s.description)}</p>
      <ul>
        <li><a href="${esc(s.website)}" target="_blank" rel="noopener">Website</a></li>
        ${(s.links || []).map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a></li>`).join("")}
      </ul>
    </article>`).join("");
  $("footSources").innerHTML = sources.filter((s) => s.website).map((s) =>
    `<li><a href="${esc(s.website)}" target="_blank" rel="noopener">${esc(s.name)}</a></li>`).join("");

  // ---------- Weergaven: publicaties of bronnen ----------
  function route() {
    const bronnen = location.hash === "#bronnen";
    $("view-publicaties").hidden = bronnen;
    $("view-bronnen").hidden = !bronnen;
    document.querySelectorAll(".nav a").forEach((a) => {
      if ((a.dataset.view === "bronnen") === bronnen) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    if (bronnen) $("bronnen-title").focus({ preventScroll: true });
  }
  window.addEventListener("hashchange", route);
  route();
})();
