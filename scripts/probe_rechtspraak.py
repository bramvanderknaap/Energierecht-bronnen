"""Tijdelijke verkenning van de open data van rechtspraak.nl (wordt niet samengevoegd)."""
import re, time, urllib.request, urllib.error

H = {"User-Agent": "Mozilla/5.0 (compatible; energierecht-bronnen/1.0; +https://github.com/)"}
BASE = "https://data.rechtspraak.nl/uitspraken/zoeken?subject=http://psi.rechtspraak.nl/rechtsgebied%23civielRecht&type=Uitspraak"


def get(url, method="GET", extra=None, limit=None):
    req = urllib.request.Request(url, headers={**H, **(extra or {})}, method=method)
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read(limit) if limit else (b"" if method == "HEAD" else r.read())
        return r.status, dict(r.headers), body


def count(url):
    st, hd, body = get(url)
    text = body.decode("utf-8", "replace")
    sub = re.search(r"<subtitle[^>]*>(.*?)</subtitle>", text)
    return text.count("<entry"), sub[1] if sub else None


print("== 1. bulkbestand ==")
for u in ["https://static.rechtspraak.nl/PI/OpenDataUitspraken.zip"]:
    try:
        st, hd, _ = get(u, "HEAD")
        print(u, st, {k: v for k, v in hd.items() if k.lower() in ("content-length", "last-modified", "accept-ranges", "content-type")})
        st, hd, body = get(u, extra={"Range": "bytes=0-99"}, limit=100)
        print("  range:", st, hd.get("Content-Range"), len(body))
    except Exception as e:
        print(u, "FOUT", type(e).__name__, e)

print("== 2. aantallen per jaar (date-bereik) ==")
for y in range(2015, 2027):
    try:
        print(y, count(f"{BASE}&date={y}-01-01&date={y}-12-31&max=1"))
    except Exception as e:
        print(y, "FOUT", e)
    time.sleep(1)
try:
    n, sub = count(f"{BASE}&date=2019-03-01&date=2019-03-31&max=1000")
    print("maart 2019, max=1000:", n, sub)
    n, sub = count(f"{BASE}&modified=2026-11-11T00:00:00&max=1000")
    print("gewijzigd sinds 11-11-2026:", n, sub)
except Exception as e:
    print("FOUT", e)

print("== 3. volledige tekst van een uitspraak ==")
for ecli in ["ECLI:NL:RBROT:2026:15790", "ECLI:NL:RBROT:2026:14000"]:
    try:
        st, hd, body = get(f"https://data.rechtspraak.nl/uitspraken/content?id={ecli}")
        t = body.decode("utf-8", "replace")
        print(ecli, st, len(t), "bytes")
        print("  subject:", re.findall(r"<dcterms:subject[^>]*>([^<]*)<", t)[:5])
        print("  references:", re.findall(r"<dcterms:references[^>]*>([^<]*)<", t)[:10])
        print("  relation:", re.findall(r"<dcterms:relation[^>]*>([^<]*)<", t)[:5])
        for w in ["Elektriciteitswet", "Gaswet", "Energiewet", "netbeheerder", "<uitspraak", "<inhoudsindicatie"]:
            print("  ", w, t.count(w))
        print(t[:2500])
    except Exception as e:
        print(ecli, "FOUT", e)
    time.sleep(1)
