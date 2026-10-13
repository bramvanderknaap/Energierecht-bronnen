"""Haalt de nieuwste publicaties op uit de bronnen in sources.json
en schrijft ze naar data/items.json. Gebruikt alleen de standaardbibliotheek."""

import json
import re
import sys
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
            self.links.append((self._href, " ".join("".join(self._text).split())))
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
        items.append({"title": text, "url": url, "date": None, "summary": ""})
    return items


def matches_keywords(item, keywords):
    if not keywords:
        return True
    text = f" {item['title']} {item['summary']} ".lower()
    return any(k.lower() in text for k in keywords)


def collect(source):
    found, report = [], []
    for feed in source.get("feeds", []):
        try:
            raw = download(feed["url"])
            if feed["type"] == "html":
                items = parse_html(raw, feed["url"], feed["include"])
            else:
                items = parse_feed(raw, feed["url"])
            report.append(f"  OK   {len(items):4d}  {feed['url']}")
            found.extend(items)
        except Exception as e:  # een kapotte bron mag de rest niet stoppen
            report.append(f"  FOUT       {feed['url']}  ({type(e).__name__}: {e})")
    kept = [i for i in found if matches_keywords(i, source.get("keywords"))]
    return kept, report


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
    for url, item in old.items():
        if url not in all_items and any(s["id"] == item.get("source") for s in sources):
            all_items[url] = item

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
