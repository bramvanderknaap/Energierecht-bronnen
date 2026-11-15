"""Tijdelijke verkenning (wordt niet samengevoegd): lettertypen, kleuren en vormen van wintervlam.eu."""
import re, urllib.request
from urllib.parse import urljoin

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


html = get("https://www.wintervlam.eu/")
inline = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
print("=== variabelen (inline) ===")
seen = set()
pat = re.compile(r"(--(?:black|white|accent|darkAccent|lightAccent|safe\w*|siteBackground\w*|heading[\w-]*|body[\w-]*|meta[\w-]*|normal-text[\w-]*|large-text[\w-]*|small-text[\w-]*|site-navigation[\w-]*|primary-button[\w-]*|secondary-button[\w-]*|tertiary-button[\w-]*|header[\w-]*|site-title[\w-]*|sqs-site[\w-]*|page-padding|sqs-site-gutter|sqs-site-max-width|horizontal[\w-]*)(?:-hsl)?)\s*:\s*([^;}{]+)")
for k, v in pat.findall(inline):
    key = (k, v.strip())
    if key in seen:
        continue
    seen.add(key)
    print(k, ":", v.strip()[:140])
print("=== context '16px 0' en radius in inline en html ===")
for m in re.finditer(r"border-radius\s*:\s*([^;}{]+)", inline):
    s = inline[max(0, m.start() - 160):m.end() + 10].replace("\n", " ")
    if "0px 0px 0px 0px" not in s:
        print("...", s[-260:])
print("=== style-attributen met radius/clip/mask in html ===")
for m in re.findall(r'style="([^"]*(?:radius|clip|mask)[^"]*)"', html)[:20]:
    print(m[:300])
print("=== shape/mask svg paden ===")
for m in re.findall(r'<clipPath[^>]*>.*?</clipPath>', html, re.S)[:6]:
    print(re.sub(r"\s+", " ", m)[:500])
print("=== sectie-achtergronden/kleurthema's ===")
for m in sorted(set(re.findall(r'data-section-theme="([^"]+)"', html))):
    print("theme", m)
for m in re.findall(r'\.(white|white-bold|light|light-bold|bright|bright-inverse|dark|dark-bold|black|black-bold)\s*\{([^}]{0,600})', inline)[:12]:
    print(m[0], m[1][:600])
print("=== eyebrow 'Wintervlam' en knoppen in html ===")
i = html.find(">Wintervlam<")
print(html[max(0, i - 700):i + 300] if i > 0 else "niet gevonden")
i = html.find("Alle expertises")
print(html[max(0, i - 900):i + 100] if i > 0 else "niet gevonden")
