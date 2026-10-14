(async function () {
  "use strict";
  const PAGE = 40;
  const TZ = "Europe/Amsterdam";
  const root = document.documentElement;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

  // Datums: alles in Nederlandse tijd, dagen als "JJJJ-MM-DD"
  const dayKey = (iso) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
  const fmt = (iso, opts) => new Date(iso).toLocaleDateString("nl-NL", { timeZone: TZ, ...opts });
  const fmtTime = (iso) => new Date(iso).toLocaleTimeString("nl-NL", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
  const keyToUTC = (k) => Date.UTC(+k.slice(0, 4), +k.slice(5, 7) - 1, +k.slice(8, 10));
  const daysBetween = (a, b) => Math.round((keyToUTC(a) - keyToUTC(b)) / 86400000);

  const BRK_ON = '<svg class="brk brk-on" viewBox="0 0 22 12" aria-hidden="true" focusable="false"><path class="brk-l" d="M1 6H21"/><rect class="brk-n" x="7" y="2" width="8" height="8"/></svg>';
  const BRK_OFF = '<svg class="brk brk-off" viewBox="0 0 22 12" aria-hidden="true" focusable="false"><path class="brk-l" d="M1 6H5.5M16.5 6H21"/><rect class="brk-n" x="7" y="2" width="8" height="8"/></svg>';
  const ICON_OPEN = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';

  // ---------- Thema ----------
  const themeBtn = $("themeBtn");
  const mqDark = matchMedia("(prefers-color-scheme: dark)");
  const effectiveTheme = () => root.getAttribute("data-theme") || (mqDark.matches ? "dark" : "light");
  function syncTheme() {
    const dark = effectiveTheme() === "dark";
    themeBtn.setAttribute("aria-pressed", String(dark));
    themeBtn.title = dark ? "Donker thema staat aan" : "Donker thema staat uit";
  }
  themeBtn.addEventListener("click", () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("eb-theme", next); } catch (e) {}
    syncTheme();
  });
  mqDark.addEventListener?.("change", syncTheme);
  syncTheme();

  // ---------- Landschap en aanzicht (decoratief, uit assets/) ----------
  const land = $("land");
  const mqNarrow = matchMedia("(max-width: 719.98px)");
  async function inject(el, url) {
    if (el.dataset.src === url) return;
    el.dataset.src = url;
    try {
      const svg = await (await fetch(url)).text();
      if (el.dataset.src === url) el.innerHTML = svg;
    } catch (e) { /* zonder tekening werkt de site gewoon */ }
  }
  const loadLand = () => inject(land, mqNarrow.matches ? "assets/landschap-smal.svg" : "assets/landschap-breed.svg");
  loadLand();
  mqNarrow.addEventListener?.("change", loadLand);
  inject($("elev"), "assets/aanzicht.svg");

  // Animaties pauzeren buiten beeld en in een verborgen tabblad
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => es.forEach((e) => e.target.classList.toggle("is-paused", !e.isIntersecting)));
    document.querySelectorAll("[data-anim]").forEach((el) => io.observe(el));
  }
  const vis = () => root.classList.toggle("tab-hidden", document.hidden);
  document.addEventListener("visibilitychange", vis);
  vis();

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
  const updated = data.updated || new Date().toISOString();
  const today = dayKey(updated);
  items.forEach((i) => { i.age = daysBetween(today, i.day); });

  // Bronnen met publicaties, in de volgorde van sources.json
  const feedSources = sources.filter((s) => items.some((i) => i.source === s.id));
  const stats = Object.fromEntries(feedSources.map((s) => {
    const own = items.filter((i) => i.source === s.id);
    const weeks = Array.from({ length: 8 }, (_, w) => own.filter((i) => i.age >= w * 7 && i.age < (w + 1) * 7).length);
    return [s.id, {
      total: own.length,
      d30: own.filter((i) => i.age < 30).length,
      week: weeks[0],
      weeks,
      last: own[0] && own[0].date,
    }];
  }));

  // ---------- Kop en "per bron" ----------
  if (data.updated) {
    $("liveTime").textContent = `${fmt(updated, { day: "numeric", month: "short" })} · ${fmtTime(updated)}`;
    $("liveTime").setAttribute("datetime", updated);
    $("live").hidden = false;
  }
  $("eyebrow").textContent = `Dagelijks · ${feedSources.length} bronnen · NL en EU`;
  
  $("wkCheck").innerHTML = data.updated ? `Bijgewerkt om <time class="mono" datetime="${esc(updated)}">${esc(fmtTime(updated))}</time>` : "";
  const total30 = feedSources.reduce((n, s) => n + stats[s.id].d30, 0);
  const totalWeek = feedSources.reduce((n, s) => n + stats[s.id].week, 0);
  $("wkRange").textContent = `${totalWeek} deze week · t/m ${fmt(updated, { day: "numeric", month: "short", year: "numeric" })}`;
  $("wkTotal").textContent = total30;
  $("wkTotalLabel").textContent = "in 30 dagen";

  const shortName = (s) => (s.id === "cbb" ? "CBb" : s.name);
  $("readouts").innerHTML = feedSources.map((s) => {
    const st = stats[s.id];
    const maxW = Math.max(1, ...st.weeks);
    const bars = st.weeks.slice().reverse().map((n, idx, arr) => {
      const h = n ? Math.max(1, Math.round((n / maxW) * 2)) : 0;
      const cls = idx === arr.length - 1 ? (n ? "now" : "z") : (n ? "" : "z");
      return `<i class="${cls}" style="--v:${h}"></i>`;
    }).join("");
    const cap = st.week
      ? `<span class="ro-cap hot">${BRK_ON}${st.week} deze week</span>`
      : `<span class="ro-cap">${BRK_OFF}Laatst: ${esc(fmt(st.last, { day: "numeric", month: "short" }))}</span>`;
    return `<li><button class="readout" type="button" aria-pressed="false" data-bron="${esc(s.id)}">
      <span class="ro-name">${esc(shortName(s))}</span>
      <span class="ro-row"><span class="ro-n">${st.d30}</span><span class="sr-only"> publicaties in 30 dagen,</span><span class="bars" aria-hidden="true">${bars}</span></span>
      ${cap}</button></li>`;
  }).join("");
  $("readouts").style.setProperty("--cols", feedSources.length);

  // ---------- Filters ----------
  const state = { bron: "alle", periode: "alles", nl: false, q: "", shown: PAGE };

  $("bronList").innerHTML = [`<li><label class="check all"><input type="radio" name="bron" value="alle" checked><span>Alle bronnen</span><span class="n">${items.length}</span></label></li>`]
    .concat(feedSources.map((s) => {
      const st = stats[s.id];
      return `<li><label class="check"><input type="radio" name="bron" value="${esc(s.id)}"><span>${esc(s.name)}</span><span class="n">${st.week ? BRK_ON : BRK_OFF}${st.total}<span class="sr-only">${st.week ? ", nieuw deze week" : ", deze week niets nieuws"}</span></span></label></li>`;
    })).join("");

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
  const liveTopics = TOPICS
    .map((t) => ({ ...t, hits: items.filter((i) => matchesQ(i, t.label)).length }))
    .filter((t) => t.hits > 0)
    .sort((a, b) => b.hits - a.hits)
    .slice(0, 6);
  if (liveTopics.length) {
    $("topics").innerHTML = liveTopics.map((t) => `<button class="chip" type="button" data-q="${esc(t.label)}">${esc(t.label)}</button>`).join("");
    $("quick").hidden = false;
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
  const mqWide = matchMedia("(min-width: 521px)");
  const placeholder = () => { zoek.placeholder = mqWide.matches ? "Zoek in titels, bijv. ‘netcode’ of ‘tarief’" : "Zoek in titels"; };
  placeholder();
  mqWide.addEventListener?.("change", placeholder);

  function filtered() {
    const maxAge = state.periode === "alles" ? Infinity : +state.periode;
    return items.filter((i) =>
      i.age < maxAge &&
      (state.bron === "alle" || i.source === state.bron) &&
      (!state.nl || geldtVoorNL(i)) &&
      matchesQ(i, state.q));
  }

  function relLabel(age) {
    if (age <= 0) return "Vandaag";
    if (age === 1) return "Gisteren";
    if (age < 7) return `${age} dagen geleden`;
    return null;
  }

  function itemHtml(i) {
    const s = byId[i.source] || { name: i.source, region: "" };
    const region = (s.region || "").split("/")[0];
    const summary = i.summary ? (i.summary.length > 220 ? i.summary.slice(0, 220).trimEnd() + "…" : i.summary) : "";
    const est = i.date_estimated ? `<span class="est">datum geschat, gevonden ${esc(fmt(i.date, { day: "numeric", month: "short" }))}</span>` : "";
    return `<li class="item${i.age < 7 ? " is-week" : ""}">
      <span class="node" aria-hidden="true"></span>
      <article class="body">
        <div class="meta"><span class="src r-${esc(region)}"><b>${esc(shortName(s))}</b><i>${esc(s.region)}</i></span>${est}</div>
        <h4><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a></h4>
        ${summary ? `<p class="sum">${esc(summary)}</p>` : ""}
        <div class="acts"><a href="${esc(i.url)}" target="_blank" rel="noopener">${ICON_OPEN}Open bij ${esc(s.name)}</a></div>
      </article>
    </li>`;
  }

  function render() {
    const list = filtered();
    const visible = list.slice(0, state.shown);
    const days = [];
    visible.forEach((i) => {
      const last = days[days.length - 1];
      if (last && last.day === i.day) last.items.push(i);
      else days.push({ day: i.day, age: i.age, iso: i.date, items: [i] });
    });
    $("tl").innerHTML = days.map((d) => {
      const rel = relLabel(d.age);
      const noon = `${d.day}T12:00:00Z`;
      const full = fmt(noon, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
      const short = fmt(noon, { weekday: "short", day: "numeric", month: "short" });
      const n = list.filter((i) => i.day === d.day).length;
      return `<li class="day${d.age <= 0 ? " is-today" : ""}">
        <div class="day-date" aria-hidden="true"><b>${esc(fmt(noon, { day: "numeric", month: "short" }))}</b><span>${esc(fmt(noon, { weekday: "short" }))} ${d.day.slice(0, 4)}</span></div>
        <span class="bus" aria-hidden="true"></span>
        <h3 class="day-title"><span class="rel">${esc(rel || fmt(noon, { day: "numeric", month: "long" }))}</span><span class="d-inline">${esc(short)}</span><time class="day-full" datetime="${d.day}">${esc(full)}</time><span class="day-meta">${n} publicatie${n === 1 ? "" : "s"}</span></h3>
        <ol class="items">${d.items.map(itemHtml).join("")}</ol>
      </li>`;
    }).join("");
    const s = byId[state.bron];
    $("count").textContent = `${list.length} publicatie${list.length === 1 ? "" : "s"}${s ? ` · alleen ${s.name}` : ""}${state.q ? ` · ‘${state.q}’` : ""}`;
    $("empty").hidden = list.length > 0;
    $("more").hidden = list.length <= state.shown;
    $("fState").textContent = `${state.periode === "alles" ? "alles" : state.periode + " dagen"} · ${s ? s.name : "alle bronnen"}${state.nl ? " · NL" : ""}`;
    document.querySelectorAll(".readout").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.bron === state.bron)));
    document.querySelectorAll("#topics .chip").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.q.toLowerCase() === state.q.toLowerCase())));
  }

  function setBron(id) {
    state.bron = id;
    const radio = form.querySelector(`input[name=bron][value="${CSS.escape(id)}"]`);
    if (radio) radio.checked = true;
    state.shown = PAGE;
    render();
  }

  form.addEventListener("change", (e) => {
    if (e.target.name === "periode") state.periode = e.target.value;
    if (e.target.name === "bron") state.bron = e.target.value;
    if (e.target.id === "alleenNL") state.nl = e.target.checked;
    state.shown = PAGE;
    render();
  });
  $("readouts").addEventListener("click", (e) => {
    const b = e.target.closest(".readout");
    if (b) setBron(state.bron === b.dataset.bron ? "alle" : b.dataset.bron);
  });
  zoek.addEventListener("input", () => { state.q = zoek.value.trim(); state.shown = PAGE; render(); });
  $("searchForm").addEventListener("submit", (e) => { e.preventDefault(); state.q = zoek.value.trim(); render(); goTimeline(); });
  $("topics").addEventListener("click", (e) => {
    const c = e.target.closest(".chip");
    if (!c) return;
    const same = state.q.toLowerCase() === c.dataset.q.toLowerCase();
    state.q = same ? "" : c.dataset.q;
    zoek.value = state.q;
    state.shown = PAGE;
    render();
    if (!same) goTimeline();
  });
  $("more").addEventListener("click", () => { state.shown += PAGE; render(); });
  $("resetBtn").addEventListener("click", () => {
    form.reset();
    Object.assign(state, { bron: "alle", periode: "alles", nl: false, q: "", shown: PAGE });
    zoek.value = "";
    render();
  });

  function goTimeline() {
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

  // ---------- Bronnen & vaste links ----------
  $("sources").innerHTML = sources.map((s) => {
    const st = stats[s.id];
    const state = st
      ? `<span class="card-state">${st.week ? BRK_ON : BRK_OFF}${st.week ? `${st.week} deze week` : `laatst ${esc(fmt(st.last, { day: "numeric", month: "short" }))}`}</span>`
      : `<span class="card-state">vaste links</span>`;
    return `<article class="card">
      <div class="card-head"><h3>${esc(s.name)}</h3><span class="badge">${esc(s.region)}</span>${state}</div>
      <p class="sub">${esc(s.full_name)}</p>
      <p>${esc(s.description)}</p>
      <ul>
        <li><a href="${esc(s.website)}" target="_blank" rel="noopener">Website</a></li>
        ${(s.links || []).map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a></li>`).join("")}
      </ul>
    </article>`;
  }).join("");
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
