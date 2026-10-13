# Tijdelijk: alle vaste links controleren
python3 - <<'PY'
import json, re, subprocess, html
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
for s in json.load(open("sources.json")):
    for l in s.get("links", []):
        out = subprocess.run(["curl", "-sL", "-A", UA, "-H", "Accept-Language: nl,en;q=0.8", "--max-time", "40", "-o", "p.html",
                              "-w", "%{http_code} %{url_effective}", l["url"]], capture_output=True, text=True).stdout
        page = open("p.html", errors="replace").read()
        t = re.search(r"<title[^>]*>([^<]*)", page)
        t = " ".join(html.unescape(t[1]).split())[:90] if t else ""
        extra = ""
        if "eur-lex" in l["url"]:
            m = re.search(r"CELEX:(\d)(\d{4})([LR])(\d{4})", l["url"])
            if m:
                num = f"{m[2]}/{int(m[4])}" if m[3] == "L" or m[2] >= "2015" else f"{int(m[4])}/{m[2]}"
                extra = f" | bevat '{num}': {num in page} | NL-tekst: {'RICHTLIJN' in page or 'VERORDENING' in page}"
        if "wetten.overheid.nl" in l["url"]:
            g = re.search(r"Geldend van [^<.]*", page)
            extra = " | " + (g[0] if g else "") + (" | VERVALLEN" if "Regeling vervallen" in page else "")
        print(f"{s['id']:12} {out} | {l['title']} | {t}{extra}")
PY
