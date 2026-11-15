"""Tijdelijke verkenning (wordt niet samengevoegd).
A: maten en vormen uit site.css van wintervlam.eu.
B: vrij te gebruiken foto's zoeken (Openverse en Wikimedia Commons) en als kleine voorbeelden opslaan in probe/."""
import json, os, re, subprocess, sys, urllib.parse, urllib.request

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
BOT = {"User-Agent": "EnergierechtBronnen-probe/1.0 (static site build)"}


def get(url, headers=H, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def part_a():
    html = get("https://www.wintervlam.eu/")
    m = re.search(r'https://static1\.squarespace\.com/static/versioned-site-css/[^"\']+?site\.css', html)
    print("site.css:", m.group(0) if m else "niet gevonden")
    css = get(m.group(0)) if m else ""
    print("lengte", len(css))
    print("=== variabelen ===")
    keys = re.compile(r"(heading|body|meta|button|nav|header|title|font|letter|line-height|size|radius|padding|spacing|gutter|max-width|accent|siteBackground)", re.I)
    seen = set()
    for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;}{]{1,160})", css):
        v = v.strip()
        if keys.search(k) and (k, v) not in seen and "var(" not in v[:4]:
            seen.add((k, v))
    for k, v in sorted(seen)[:400]:
        print(k, ":", v)
    print("=== border-radius niet nul ===")
    for mm in re.finditer(r"([^{}]{0,160})\{([^{}]*border-radius\s*:\s*(?!0[;}\s]|0px)[^;}]+[^{}]*)\}", css):
        print(mm.group(1).strip()[-160:], "{", re.sub(r"\s+", " ", mm.group(2))[:300], "}")
    print("=== laatste 4000 tekens (eigen CSS) ===")
    print(css[-4000:])
    print("=== vormen in html ===")
    for mm in re.finditer(r"(image-shape|sqs-shape|data-shape|shape-type|has-shape|clip-path)", html):
        print("...", re.sub(r"\s+", " ", html[max(0, mm.start() - 200):mm.end() + 300]))
    print("=== Wintervlam-label en kop ===")
    for mm in list(re.finditer(r"Wintervlam\s*</", html))[:4]:
        print("...", re.sub(r"\s+", " ", html[max(0, mm.start() - 500):mm.end() + 200]))
    i = html.find("voorop")
    print("hero:", re.sub(r"\s+", " ", html[max(0, i - 600):i + 200]) if i > 0 else "niet gevonden")


QUERIES = {
    "turbine": ["wind turbine blue sky", "wind turbine low angle", "wind turbine from below"],
    "mast": ["high voltage pylon sky", "electricity pylon blue sky", "transmission tower"],
    "zon": ["solar park aerial", "solar farm aerial view", "photovoltaic power station aerial"],
    "extra": ["offshore wind farm", "power lines sunset", "wind farm netherlands"],
}
OK_LICENSE = re.compile(r"^(cc0|pdm|public domain|cc by( |-)?(2\.0|2\.5|3\.0|4\.0)?$|cc by-sa)", re.I)


def openverse(q):
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        {"q": q, "license": "cc0,pdm,by,by-sa", "page_size": 14, "size": "large", "aspect_ratio": "wide", "mature": "false"})
    out = []
    try:
        res = json.loads(get(url, BOT))
    except Exception as e:
        print("openverse fout", q, e)
        return out
    for r in res.get("results", []):
        out.append({"bron": "openverse", "titel": r.get("title"), "maker": r.get("creator"),
                    "licentie": f"{r.get('license')} {r.get('license_version') or ''}".strip(),
                    "pagina": r.get("foreign_landing_url"), "origineel": r.get("url"),
                    "thumb": r.get("thumbnail"), "b": r.get("width"), "h": r.get("height")})
    return out


def commons(q):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": q + " filetype:bitmap", "gsrlimit": 14, "prop": "imageinfo",
        "iiprop": "url|size|extmetadata", "iiurlwidth": 480})
    out = []
    try:
        res = json.loads(get(url, BOT))
    except Exception as e:
        print("commons fout", q, e)
        return out
    for p in (res.get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        artist = re.sub("<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", ""))
        if ii.get("width", 0) < 2000 or ii.get("width", 0) < ii.get("height", 1):
            continue
        out.append({"bron": "commons", "titel": p.get("title"), "maker": artist.strip(), "licentie": lic,
                    "pagina": ii.get("descriptionurl"), "origineel": ii.get("url"), "thumb": ii.get("thumburl"),
                    "b": ii.get("width"), "h": ii.get("height")})
    return out


def part_b():
    from PIL import Image
    import io
    os.makedirs("probe", exist_ok=True)
    alle = {}
    for cat, qs in QUERIES.items():
        n = 0
        lijst = []
        for q in qs:
            for r in openverse(q) + commons(q):
                if not OK_LICENSE.search(r["licentie"] or ""):
                    continue
                if any(x["origineel"] == r["origineel"] for x in lijst):
                    continue
                src = r["thumb"] or r["origineel"]
                try:
                    data = get(src, BOT, binary=True)
                    im = Image.open(io.BytesIO(data)).convert("RGB")
                    im.thumbnail((480, 320))
                    n += 1
                    naam = f"probe/{cat}-{n:02d}.jpg"
                    im.save(naam, quality=70)
                    r["bestand"] = naam
                    lijst.append(r)
                except Exception as e:
                    print("thumb fout", src, e)
                if n >= 28:
                    break
            if n >= 28:
                break
        alle[cat] = lijst
        print(cat, n, "voorbeelden")
    with open("probe/fotos.json", "w") as f:
        json.dump(alle, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if "a" in sys.argv[1:]:
        part_a()
    if "b" in sys.argv[1:]:
        part_b()
