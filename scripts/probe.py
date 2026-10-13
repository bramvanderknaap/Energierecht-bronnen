"""Hulpscript: toont alle links en feeds op de opgegeven pagina's (voor het instellen van bronnen)."""
import re
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from fetch import HEADERS, LinkParser  # noqa: E402
from urllib.parse import urljoin  # noqa: E402

for url in sys.argv[1:]:
    print(f"\n===== {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            print("final url:", r.geturl())
    except Exception as e:
        print("FOUT", e)
        continue
    for m in re.findall(r"<link[^>]+(?:rss|atom)[^>]*>", raw, re.I):
        print("FEED", m)
    for m in re.findall(r"<time[^>]*>[^<]*</time>", raw)[:5]:
        print("TIME", m)
    p = LinkParser()
    p.feed(raw)
    for href, text in p.links:
        print("LINK", urljoin(url, href or ""), "|", text[:100])
