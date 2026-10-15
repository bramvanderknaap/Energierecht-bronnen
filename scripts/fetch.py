"""Haalt de nieuwste publicaties op uit de bronnen in sources.json
en schrijft ze naar data/items.json. Gebruikt alleen de standaardbibliotheek."""

import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources.json"
OUTPUT = ROOT / "data" / "items.json"
MAX_PER_SOURCE = 150
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; energierecht-bronnen/1.0; +https://github.com/)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "nl,en;q=0.8",
}


def download(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def child_text(el, *names):
    for c in el:
        if local(c.tag) in names and (c.text or "").strip():
            return c.text.strip()
    return ""


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        d = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def strip_html(text):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def parse_feed(raw, base_url):
    root = ET.fromstring(raw)
    items = []
    for el in root.iter():
        kind = local(el.tag)
        if kind not in ("item", "entry"):
            continue
        title = strip_html(child_text(el, "title"))
        link = ""
        for c in el:
            if local(c.tag) == "link":
                href = c.get("href")
                if href and c.get("rel", "alternate") == "alternate":
                    link = href
                    break
                if not href and (c.text or "").strip():
                    link = c.text.strip()
                    break
        if not link:
            link = child_text(el, "guid", "id")
        summary = strip_html(child_text(el, "description", "summary", "content"))
        date = parse_date(child_text(el, "pubDate", "published", "updated", "date", "issued"))
        if title and link.startswith("http"):
            items.append({"title": title, "url": urljoin(base_url, link), "date": date, "summary": summary[:400]})
    return items


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            # Een link bevat soms een kop plus een intro; neem dan alleen de kop.
            parts = [" ".join(p.split()) for p in self._text if p.strip()]
            title = next((p for p in parts if len(p) >= 15), " ".join(parts))
            self.links.append((self._href, title))
            self._href = None


def parse_html(raw, base_url, include):
    parser = LinkParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    pattern = re.compile(include)
    items, seen = [], set()
    for href, text in parser.links:
        url = urljoin(base_url, href).split("#")[0]
        if not pattern.search(url) or url in seen or len(text) < 15:
            continue
        seen.add(url)
        m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        date = f"{m[1]}-{m[2]}-{m[3]}T00:00:00+00:00" if m else None
        items.append({"title": text, "url": url, "date": date, "summary": ""})
    return items


def matches_keywords(item, keywords, whole_words=()):
    """Een trefwoord telt als een woord ermee begint ("warmte" vindt ook "warmtenet").
    Afkortingen in whole_words tellen alleen als heel woord ("tek" niet in "tekortkoming")."""
    if not keywords:
        return True
    text = f"{item['title']} {item['summary']}".lower()
    for k in keywords:
        end = r"\b" if k in whole_words else ""
        if re.search(r"\b" + re.escape(k.lower()) + end, text):
            return True
    return False


def date_from_title(item):
    """De titel in de rechtspraak-feed bevat de datum van de uitspraak:
    "ECLI:NL:CBB:2026:490, College van Beroep voor het bedrijfsleven, 13-10-2026, 23/1443".
    De datum in de feed zelf is de datum van de laatste wijziging, dus die klopt niet."""
    m = re.search(r",\s*(\d{2})-(\d{2})-(\d{4})\s*(?:,|$)", item["title"])
    try:
        date = datetime(int(m[3]), int(m[2]), int(m[1]), tzinfo=timezone.utc).isoformat() if m else None
    except ValueError:
        date = None
    if date:
        item["date"] = date
        item["date_checked"] = True
    return item


def title_from_summary(item, prefix):
    """Rechtspraak-titels zijn alleen een ECLI-nummer; maak er een leesbare titel van."""
    first = item["summary"].rstrip(".;")
    if len(first) > 140:
        first = first[:140].rsplit(" ", 1)[0] + "…"
    ecli = item["title"].split(",")[0]
    if first:
        item["title"] = f"{prefix}: {first} ({ecli})"
    return item


def collect(source):
    found, report = [], []
    for feed in source.get("feeds", []):
        time.sleep(3)  # vriendelijk blijven voor de websites
        try:
            if feed["type"] == "hvj":
                items = hvj_judgments(feed)
                report.append(f"  OK   {len(items):4d}  {feed['url']}")
                found.extend(items)
                continue
            raw = download(feed["url"])
            if feed["type"] == "html":
                items = parse_html(raw, feed["url"], feed["include"])
            else:
                items = parse_feed(raw, feed["url"])
                if feed.get("date_from_title"):
                    items = [date_from_title(i) for i in items]
                if feed.get("title_from_summary"):
                    items = [title_from_summary(i, feed.get("title_prefix", "")) for i in items]
            report.append(f"  OK   {len(items):4d}  {feed['url']}")
            found.extend(items)
        except Exception as e:  # een kapotte bron mag de rest niet stoppen
            report.append(f"  FOUT       {feed['url']}  ({type(e).__name__}: {e})")
    kept = [i for i in found if matches_keywords(i, source.get("keywords"), source.get("whole_words", ()))]
    return kept, report


HVJ_QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?celex (MIN(?d) AS ?date) (SAMPLE(?nl) AS ?title_nl) (SAMPLE(?en) AS ?title_en) WHERE {{
  {{ ?w cdm:resource_legal_is_about_subject-matter <http://publications.europa.eu/resource/authority/subject-matter/ENER> }}
  UNION {{ ?w cdm:work_cites_work ?act . ?act cdm:resource_legal_id_celex ?ac . FILTER(STR(?ac) IN ({acts})) }}
  UNION {{ ?t cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/NLD> ;
             cdm:expression_title ?tt . FILTER(REGEX(?tt, "{words}", "i")) }}
  ?w cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?d .
  FILTER(REGEX(STR(?celex), "^6[0-9]{{4}}(CJ|TJ)[0-9]{{4}}$") && ?d >= "{since}"^^xsd:date)
  OPTIONAL {{ ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/NLD> ; cdm:expression_title ?nl }}
  OPTIONAL {{ ?f cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ; cdm:expression_title ?en }}
}} GROUP BY ?celex ORDER BY DESC(?date) LIMIT {limit}"""


def hvj_judgments(feed):
    """Arresten van het Hof van Justitie en het Gerecht uit de databank van het Publicatiebureau (Cellar).
    Relevant is een arrest als het Publicatiebureau het onder het onderwerp Energie indeelt, als het naar een
    van de energierichtlijnen of -verordeningen in "acts" verwijst, of als de titel een van de "title_words" bevat.
    Die laatste twee vangen ook nieuwe arresten, waarvoor het onderwerp vaak pas maanden later wordt ingevuld."""
    query = HVJ_QUERY.format(
        acts=",".join(f'"{a}"' for a in feed["acts"]),
        words="|".join(feed["title_words"]),
        since=feed["since"],
        limit=feed.get("limit", 150),
    )
    url = feed["url"] + "?" + urlencode({"query": query, "format": "application/sparql-results+json"})
    req = urllib.request.Request(url, headers={**HEADERS, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        rows = json.load(resp)["results"]["bindings"]
    return [hvj_item(r) for r in rows]


def hvj_item(row):
    """De titel van een arrest bestaat uit delen gescheiden door '#': soort arrest en datum, partijen,
    eventueel de verwijzende rechter, trefwoorden en het zaaknummer. Toon partijen en zaaknummer als titel."""
    celex = row["celex"]["value"]
    court = "C" if celex[5:7] == "CJ" else "T"
    case = f"{court}-{int(celex[7:11])}/{celex[3:5]}"
    full = (row.get("title_nl") or row.get("title_en") or {}).get("value", "")
    parts = [p.strip() for p in full.split("#") if p.strip()]
    parties = parts[1].rstrip(".") if len(parts) > 1 else "Arrest"
    if len(parties) > 140:
        parties = parties[:140].rsplit(" ", 1)[0] + "…"
    rest = [p for p in parts[:1] + parts[2:] if not re.match(r"(Zaak|Zaken|Gevoegde zaken|Case|Joined cases)\b", p)]
    return {
        "title": f"{parties} ({case})",
        "url": f"https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:{celex}",
        "date": f"{row['date']['value'][:10]}T00:00:00+00:00",
        "summary": " ".join(rest)[:600],
    }


MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
    "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "august": 8, "october": 10,
}
MAX_DATE_LOOKUPS = 80


def find_date(raw, structured_only=False):
    """Zoekt de publicatiedatum op de pagina van een artikel.
    structured_only: alleen de datum die de website zelf als publicatiedatum opgeeft."""
    html = raw.decode("utf-8", errors="replace")
    meta = re.search(
        r'<meta[^>]+(?:property|name)="(?:article:published_time|dcterms\.(?:created|issued|date)|DC\.date|date|publication_date)"[^>]*content="([^"]+)"',
        html, re.I) or re.search(
        r'<meta[^>]+content="([^"]+)"[^>]*(?:property|name)="(?:article:published_time|dcterms\.(?:created|issued|date)|DC\.date|date|publication_date)"',
        html, re.I)
    for m in (meta, re.search(r'"datePublished"\s*:\s*"([^"]+)"', html),
              None if structured_only else re.search(r'<time[^>]+datetime="([^"]+)"', html, re.I)):
        if m and (d := parse_date(m[1][:25])):
            return d
    if structured_only:
        return None
    # Anders: de eerste geschreven datum in de hoofdtekst, bijv. "13 oktober 2026".
    start = max(html.find("<main"), html.find("<h1"), 0)
    text = strip_html(html[start:start + 20000]).lower()
    names = "|".join(MONTHS)
    for m in re.finditer(rf"\b(\d{{1,2}}) ({names}) (20\d\d)\b|\b({names}) (\d{{1,2}}),? (20\d\d)\b|\b(\d{{1,2}})[-/.](\d{{1,2}})[-/.](20\d\d)\b", text):
        try:
            if m[1]:
                d = datetime(int(m[3]), MONTHS[m[2]], int(m[1]))
            elif m[4]:
                d = datetime(int(m[6]), MONTHS[m[4]], int(m[5]))
            else:
                d = datetime(int(m[9]), int(m[8]), int(m[7]))
        except ValueError:
            continue
        return d.replace(tzinfo=timezone.utc).isoformat()
    return None


def is_plausible(date):
    """Een publicatiedatum ligt niet in de toekomst (dan is het bijv. een deadline)."""
    return date and datetime.fromisoformat(date) <= datetime.now(timezone.utc) + timedelta(days=1)


def date_from_url(url):
    """Sommige adressen bevatten de publicatiedatum, bijv. ...-2026-09-17_en of ddn-20260922-1."""
    m = re.search(r"-(20\d\d)-(\d\d)-(\d\d)_[a-z]{2}$", url) or re.search(r"/ddn-(20\d\d)(\d\d)(\d\d)-", url)
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc).isoformat() if m else None
    except ValueError:
        return None


RECHTSPRAAK_META = "https://data.rechtspraak.nl/uitspraken/content?id={}&return=META"


def rechtspraak_date(item):
    """Haalt de uitspraakdatum op uit de gegevens van rechtspraak.nl (op ECLI-nummer)."""
    m = re.search(r"ECLI:[A-Z]{2}:[A-Z0-9]+:\d{4}:[A-Z0-9.]+", item["url"])
    if not m:
        item["date_checked"] = True
        return False
    try:
        raw = download(RECHTSPRAAK_META.format(m[0])).decode("utf-8", errors="replace")
    except Exception:
        item["date_lookups"] = item.get("date_lookups", 0) + 1
        if item["date_lookups"] >= 3:
            item["date_checked"] = True
        return False
    found = re.search(r'<dcterms:date[^>]*Uitspraakdatum[^>]*>\s*(\d{4}-\d{2}-\d{2})', raw)
    item["date_checked"] = True
    item.pop("date_lookups", None)
    if found and is_plausible(date := datetime.fromisoformat(found[1]).replace(tzinfo=timezone.utc).isoformat()):
        changed = date[:10] != item["date"][:10]
        item["date"] = date
        item.pop("date_estimated", None)
        return changed
    return False


def verify_date(item):
    """De feed van de Europese Commissie geeft de datum van de laatste wijziging, niet van publicatie.
    Lees daarom de publicatiedatum van de artikelpagina (of uit het adres)."""
    url_date = date_from_url(item["url"])
    reference = datetime.fromisoformat(url_date or item["date"])
    try:
        page_date = find_date(download(item["url"]), structured_only=True)
    except Exception:
        item["date_lookups"] = item.get("date_lookups", 0) + 1
        if url_date:
            item["date"] = url_date
            item.pop("date_estimated", None)
        if item["date_lookups"] >= 3:
            item["date_checked"] = True
        return False
    # Een publicatiedatum ligt niet na de feeddatum en niet veel eerder; anders klopt de pagina niet.
    if is_plausible(page_date) and reference - timedelta(days=60) <= datetime.fromisoformat(page_date) <= reference + timedelta(days=1):
        date = page_date
    else:
        date = url_date
    item["date_checked"] = True
    item.pop("date_lookups", None)
    if date:
        changed = date[:10] != item["date"][:10]
        item["date"] = date
        item.pop("date_estimated", None)
        return changed
    return False


def fill_dates(items, sources):
    """Haalt voor items zonder datum de datum van de artikelpagina op,
    en controleert bij bronnen met "verify" of de datum uit de feed klopt."""
    estimate = {s["id"] for s in sources if s.get("date_from_page") is True}
    verify = {s["id"] for s in sources if s.get("date_from_page") == "verify"}
    rechtspraak = {s["id"] for s in sources if s.get("date_from_page") == "rechtspraak"}
    todo = [i for i in items if i.get("date_estimated") and i["source"] in estimate and i.get("date_lookups", 0) < 3]
    check = [i for i in items if i["source"] in verify | rechtspraak and not i.get("date_checked")]
    budget = MAX_DATE_LOOKUPS
    found = 0
    for item in todo[:budget]:
        time.sleep(1)
        try:
            date = find_date(download(item["url"]))
        except Exception:
            date = None
        if is_plausible(date):
            item["date"] = date
            item.pop("date_estimated", None)
            item.pop("date_lookups", None)
            found += 1
        else:
            item["date_lookups"] = item.get("date_lookups", 0) + 1
    print(f"Publicatiedatum gevonden voor {found} van {min(len(todo), budget)} artikelen")
    budget -= min(len(todo), budget)
    corrected = 0
    for item in check[:budget]:
        time.sleep(1)
        corrected += rechtspraak_date(item) if item["source"] in rechtspraak else verify_date(item)
    print(f"Datum gecontroleerd voor {min(len(check), budget)} artikelen, {corrected} verbeterd")


def sitemap_dates(url, limit=20):
    """Leest de 'laatst gewijzigd'-datums uit een sitemap (ook als die over meerdere pagina's verdeeld is)."""
    dates, queue, seen = {}, [url], set()
    while queue and len(seen) < limit:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        try:
            root = ET.fromstring(download(current))
        except Exception as e:
            print(f"  Sitemap niet gelezen: {current} ({type(e).__name__})")
            continue
        for el in root:
            loc, lastmod = child_text(el, "loc"), child_text(el, "lastmod")
            if local(el.tag) == "sitemap" and loc:
                queue.append(loc)
            elif loc and lastmod:
                dates[loc.rstrip("/")] = parse_date(lastmod)
    return dates


def apply_sitemap_dates(items, sources):
    """Voor bronnen zonder datum op de pagina: gebruik de datum uit de sitemap van de website."""
    for source in sources:
        if not source.get("date_sitemap"):
            continue
        dates = sitemap_dates(source["date_sitemap"])
        found = 0
        for item in items:
            if item["source"] != source["id"]:
                continue
            date = dates.get(item["url"].rstrip("/"))
            if is_plausible(date):
                item["date"] = date
                item.pop("date_estimated", None)
                found += 1
            else:
                item["date"] = item["first_seen"]
                item["date_estimated"] = True
        print(f"{source['name']}: datum uit sitemap voor {found} artikelen ({len(dates)} pagina's in sitemap)")


def main():
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    old = {}
    if OUTPUT.exists():
        for item in json.loads(OUTPUT.read_text(encoding="utf-8")).get("items", []):
            old[item["url"]] = item
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    all_items = {}
    for source in sources:
        items, report = collect(source)
        print(f"{source['name']}: {len(items)} relevante items")
        print("\n".join(report))
        for item in items:
            prev = old.get(item["url"], {})
            item["source"] = source["id"]
            item["first_seen"] = prev.get("first_seen", now)
            if prev.get("date_checked"):  # eerder gecontroleerde datum niet overschrijven met de feeddatum
                item["date"] = prev["date"]
                item["date_checked"] = True
            if not item["date"]:
                item["date"] = prev.get("date") or item["first_seen"]
                item["date_estimated"] = prev.get("date_estimated", True)
            all_items.setdefault(item["url"], item)

    # Oude items bewaren die nu niet meer in de feed staan.
    by_id = {s["id"]: s for s in sources}
    for url, item in old.items():
        source = by_id.get(item.get("source"))
        if url not in all_items and source and matches_keywords(item, source.get("keywords"), source.get("whole_words", ())):
            all_items[url] = item

    apply_sitemap_dates(list(all_items.values()), sources)
    fill_dates(list(all_items.values()), sources)

    result = []
    for source in sources:
        mine = [i for i in all_items.values() if i["source"] == source["id"]]
        mine.sort(key=lambda i: i["date"], reverse=True)
        result.extend(mine[:MAX_PER_SOURCE])
    result.sort(key=lambda i: i["date"], reverse=True)

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"updated": now, "items": result}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"\nTotaal: {len(result)} items opgeslagen in {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
