"""Haalt de nieuwste publicaties op uit de bronnen in sources.json
en schrijft ze naar data/items.json. Gebruikt alleen de standaardbibliotheek."""

import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

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


def matches_keywords(item, keywords):
    if not keywords:
        return True
    text = f"{item['title']} {item['summary']}".lower()
    return any(re.search(r"\b" + re.escape(k.lower()), text) for k in keywords)


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
            raw = download(feed["url"])
            if feed["type"] == "html":
                items = parse_html(raw, feed["url"], feed["include"])
            else:
                items = parse_feed(raw, feed["url"])
                if feed.get("title_from_summary"):
                    items = [title_from_summary(i, feed.get("title_prefix", "")) for i in items]
            report.append(f"  OK   {len(items):4d}  {feed['url']}")
            found.extend(items)
        except Exception as e:  # een kapotte bron mag de rest niet stoppen
            report.append(f"  FOUT       {feed['url']}  ({type(e).__name__}: {e})")
    kept = [i for i in found if matches_keywords(i, source.get("keywords"))]
    return kept, report


MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
    "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "august": 8, "october": 10,
}
MAX_DATE_LOOKUPS = 80


def find_date(raw):
    """Zoekt de publicatiedatum op de pagina van een artikel."""
    html = raw.decode("utf-8", errors="replace")
    meta = re.search(
        r'<meta[^>]+(?:property|name)="(?:article:published_time|dcterms\.(?:created|issued|date)|DC\.date|date|publication_date)"[^>]*content="([^"]+)"',
        html, re.I) or re.search(
        r'<meta[^>]+content="([^"]+)"[^>]*(?:property|name)="(?:article:published_time|dcterms\.(?:created|issued|date)|DC\.date|date|publication_date)"',
        html, re.I)
    for m in (meta, re.search(r'"datePublished"\s*:\s*"([^"]+)"', html),
              re.search(r'<time[^>]+datetime="([^"]+)"', html, re.I)):
        if m and (d := parse_date(m[1][:25])):
            return d
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


def fill_dates(items):
    """Haalt voor items zonder datum de datum van de artikelpagina op."""
    todo = [i for i in items if i.get("date_estimated") and i.get("date_lookups", 0) < 3]
    found = 0
    for item in todo[:MAX_DATE_LOOKUPS]:
        time.sleep(1)
        try:
            date = find_date(download(item["url"]))
        except Exception:
            date = None
        if date:
            item["date"] = date
            item.pop("date_estimated", None)
            item.pop("date_lookups", None)
            found += 1
        else:
            item["date_lookups"] = item.get("date_lookups", 0) + 1
    print(f"Publicatiedatum gevonden voor {found} van {min(len(todo), MAX_DATE_LOOKUPS)} artikelen")


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
            if not item["date"]:
                item["date"] = prev.get("date") or item["first_seen"]
                item["date_estimated"] = prev.get("date_estimated", True)
            all_items.setdefault(item["url"], item)

    # Oude items bewaren die nu niet meer in de feed staan.
    by_id = {s["id"]: s for s in sources}
    for url, item in old.items():
        source = by_id.get(item.get("source"))
        if url not in all_items and source and matches_keywords(item, source.get("keywords")):
            all_items[url] = item

    fill_dates(list(all_items.values()))

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
