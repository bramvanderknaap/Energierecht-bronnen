"""Tijdelijke verkenning (wordt niet samengevoegd): lettertypen, kleuren en vormen van wintervlam.eu."""
import re, urllib.request
from collections import Counter
from urllib.parse import urljoin

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


html = get("https://www.wintervlam.eu/")
print("HTML", len(html))
links = re.findall(r'<link[^>]+href="([^"]+)"[^>]*>', html)
for l in links:
    if any(k in l for k in ("css", "font", "typekit", "googleapis")):
        print("LINK", l)
for s in re.findall(r'<script[^>]+src="([^"]+)"', html)[:30]:
    if "typekit" in s or "font" in s:
        print("SCRIPT", s)
print("--- inline style blocks ---")
inline = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
print(len(inline))
css = inline
for l in links:
    if ".css" in l or "fonts.googleapis" in l or "typekit" in l:
        try:
            c = get(urljoin("https://www.wintervlam.eu/", l))
            print("CSS", l, len(c))
            css += "\n" + c
        except Exception as e:
            print("CSS FOUT", l, e)
ff = Counter(m.strip() for m in re.findall(r"font-family\s*:\s*([^;}{]+)", css))
print("--- font-family ---")
for k, v in ff.most_common(25):
    print(v, k[:120])
print("--- @font-face ---")
for block in re.findall(r"@font-face\s*{[^}]*}", css)[:30]:
    print(re.sub(r"\s+", " ", block)[:300])
print("--- font-weight ---", Counter(re.findall(r"font-weight\s*:\s*([^;}{]+)", css)).most_common(10))
print("--- letter-spacing ---", Counter(re.findall(r"letter-spacing\s*:\s*([^;}{]+)", css)).most_common(10))
print("--- border-radius ---", Counter(re.findall(r"border-radius\s*:\s*([^;}{]+)", css)).most_common(15))
print("--- kleuren hex ---", Counter(c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", css)).most_common(25))
print("--- hsl ---", Counter(re.findall(r"hsla?\([^)]+\)", css)).most_common(25))
print("--- custom properties ---")
for k, v in Counter(re.findall(r"(--[\w-]+)\s*:\s*([^;}{]{1,80})", css)).most_common(80):
    print(k)
print("--- tweak / theme json ---")
for m in re.findall(r'"(?:fontFamily|font-family|headingFont|bodyFont|fontName)"\s*:\s*"([^"]+)"', html)[:20]:
    print("JSON font", m)
for m in re.findall(r'(?:heading|body|button|meta|navigation)[A-Za-z-]*Font[A-Za-z-]*["\']?\s*[:=]\s*["\']?([^"\',;}]+)', html)[:30]:
    print("TWEAK", m)
print("--- afbeeldingen/video ---")
for m in sorted(set(re.findall(r'https://[^"\'\s)]+\.(?:jpg|jpeg|png|webp|mp4|svg)', html)))[:30]:
    print(m)
print("--- tekst kop ---")
for m in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.S)[:12]:
    print(re.sub(r"<[^>]+>", "", m).strip()[:100], "|", m[:200])
