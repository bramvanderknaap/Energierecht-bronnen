"""Civiele uitspraken over energierecht uit de open data van rechtspraak.nl.

De zoekfunctie van rechtspraak.nl geeft alleen het ECLI-nummer en de samenvatting (inhoudsindicatie).
Daarom wordt van elke civiele uitspraak de volledige tekst opgehaald en daarin gezocht naar:
- verwijzingen naar energiewetgeving (Elektriciteitswet 1998, Gaswet, Energiewet, Warmtewet, ...),
- energiebedrijven als procespartij (leveranciers, netbeheerders, producenten),
- energiebegrippen in de samenvatting of herhaaldelijk in de tekst.
Zaken over hennepteelt vallen af."""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "civiel"
STATE = ARCHIVE / "stand.json"
START_YEAR = 2019
MAX_PER_RUN = 4000  # dagelijkse run: maximaal zoveel gewijzigde uitspraken controleren

SEARCH = ("https://data.rechtspraak.nl/uitspraken/zoeken?subject=http://psi.rechtspraak.nl/rechtsgebied%23civielRecht"
          "&type=Uitspraak&return=DOC")
CONTENT = "https://data.rechtspraak.nl/uitspraken/content?id={}"
DETAILS = "https://uitspraken.rechtspraak.nl/details?id={}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; energierecht-bronnen/1.0; +https://github.com/)"}

# Energiewetgeving: één vermelding in de tekst is genoeg.
LAWS = [
    "elektriciteitswet", "gaswet", "energiewet", "warmtewet", "wet collectieve warmte", "mijnbouwwet",
    "wet windenergie op zee", "netcode elektriciteit", "tarievencode", "begrippencode", "meetcode",
    "informatiecode", "systeemcode", "aansluit- en transportcode", "regeling afnemers en monitoring",
    "besluit factuur, verbruiks- en indicatief kostenoverzicht", "warmtebesluit", "warmteregeling",
    "mijnbouwbesluit", "tijdelijke wet groningen", "besluit aanleg energie-infrastructuur",
    "wet voortgang energietransitie", "besluit leveringszekerheid", "regeling inzake tariefstructuren",
    "stimulering duurzame energie", "wet opslag duurzame energie",
]
# Energiebedrijven die als partij herkenbaar zijn aan hun naam.
COMPANIES = [
    "eneco", "essent", "vattenfall", "nuon", "greenchoice", "vandebron", "energiedirect", "budget energie",
    "oxxio", "engie", "electrabel", "delta energie", "pure energie", "frank energie", "united consumers",
    "main energie", "innova energie", "mega energie", "coolblue energie", "zonneplan", "tibber", "anwb energie",
    "easyenergy", "nextenergy", "qurrent", "powerpeers", "energie vanons", "hollandse energie maatschappij",
    "nederlandse energie maatschappij", "agem", "gulf gas", "e.on", "rwe", "uniper", "tennet", "stedin",
    "liander", "alliander", "enexis", "westland infra", "coteq", "rendo", "gasunie", "gasterra",
    "energie beheer nederland", "nederlandse aardolie maatschappij", "ennatuurlijk", "eteck", "procent energie",
    "energiecollectief", "inkoopcollectief",
]
KNOWN_COMPANIES = re.compile(r"\b(" + "|".join(re.escape(c) for c in COMPANIES) + r")\b", re.I)
# Andere bedrijfsnamen met energie, energy of solar erin tellen alleen als de tekst ook over energie gaat.
OTHER_COMPANIES = re.compile(
    r"[\w&'.-]*(energie|energy|netbeheer|windpark|zonnepark|solar)[\w&'.-]*(\s+[\w&'.-]+){0,3}\s+(b\.v\.|n\.v\.|u\.a\.)",
    re.I)
# In deze zaken is een energiebedrijf meestal alleen schuldeiser of werkgever.
NO_PARTY_SUBJECTS = ("insolventierecht", "arbeidsrecht", "personen- en familierecht")
# Energiebegrippen die meetellen in de samenvatting.
TERMS = [
    "energieleverancier", "energiebedrijf", "energiecontract", "energieovereenkomst", "energielevering",
    "energierekening", "energieprijs", "energietarie", "levering van elektriciteit", "levering van gas",
    "levering van energie", "levering energie", "elektriciteitslevering", "gaslevering", "stroomlevering",
    "netbeheerder", "netaansluiting", "aansluit- en transportovereenkomst", "transportcapaciteit",
    "transportvermogen", "netcongestie", "stroomstoring", "gasaansluiting", "elektriciteitsaansluiting",
    "warmtenet", "warmtelevering", "warmteleverancier", "stadsverwarming", "zonnepark", "zonne-energie",
    "windturbine", "windpark", "windmolen", "windenergie", "laadpa", "laadpunt", "laadinfrastructuur",
    "terugleverkosten", "terugleververgoeding", "teruglevering van elektriciteit", "salderingsregeling",
    "energieopslag", "biogas", "kernenergie", "gaswinning", "aardbevingsschade", "mijnbouwschade",
    "mijnbouw", "energietransitie", "warmtekrachtkoppeling", "energiehandel", "energiecollectief",
    "inkoopcollectief",
]
# Kernbegrippen: een uitspraak die er vijf keer of vaker een noemt, gaat over energie.
CORE = [
    "netbeheerder", "aansluit- en transportovereenkomst", "transportcapaciteit", "transportvermogen",
    "netcongestie", "gaswinning", "aardbevingsschade", "mijnbouwschade", "energieleverancier",
    "warmteleverancier", "warmtelevering", "levering van elektriciteit", "levering van gas",
    "levering van energie", "energiecontract", "energieovereenkomst",
]
CORE_THRESHOLD = 5
EXCLUDE = ["hennep", "cannabis", "growshop", "wietplant", "wietteelt", "wietkwekerij"]


def download(url, attempts=4):
    """Eén verzoek tegelijk (vraag van rechtspraak.nl); bij een storing even wachten en opnieuw."""
    for n in range(attempts):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if n == attempts - 1 or (isinstance(e, urllib.error.HTTPError) and e.code == 404):
                raise
            time.sleep(10 * (n + 1))


def local(tag):
    return tag.rsplit("}", 1)[-1]


def search(**params):
    """Alle civiele uitspraken (met tekst) voor een zoekopdracht, in pagina's van 1000.
    params: date=(van, tot) of modified=(van, tot); waarden in de vorm die rechtspraak.nl verwacht."""
    query = [(k, v) for k, vals in params.items() for v in vals]
    found, start = [], 0
    while True:
        raw = download(f"{SEARCH}&{urlencode(query + [('max', 1000), ('from', start)])}")
        page = []
        for el in ET.fromstring(raw):
            if local(el.tag) != "entry":
                continue
            fields = {local(c.tag): (c.text or "").strip() for c in el}
            page.append({"ecli": fields.get("id") or fields.get("title", "").split(",")[0].strip(),
                         "updated": fields.get("updated", "")})
        found += page
        if len(page) < 1000:
            return found
        start += 1000
        time.sleep(1)


def fetch_ruling(ecli):
    """Metadata, samenvatting en volledige tekst van één uitspraak."""
    root = ET.fromstring(download(CONTENT.format(ecli)))
    r = {"ecli": ecli, "instantie": "", "datum": "", "gepubliceerd": "", "subject": [], "summary": "", "text": ""}
    for el in root.iter():
        name = local(el.tag)
        if name == "creator" and not r["instantie"]:
            r["instantie"] = (el.text or "").strip()
        elif name == "date" and "Uitspraakdatum" in str(el.attrib.values()):
            r["datum"] = (el.text or "").strip()
        elif name == "issued" and not r["gepubliceerd"]:
            r["gepubliceerd"] = (el.text or "").strip()[:10]
        elif name == "subject":
            r["subject"].append((el.text or "").strip())
        elif name == "inhoudsindicatie":
            r["summary"] = " ".join(" ".join(el.itertext()).split())
        elif name in ("uitspraak", "conclusie") and not r["text"]:
            r["text"] = " ".join(" ".join(el.itertext()).split())
    return r


def header(text):
    """Het begin van de uitspraak met de partijen, tot het procesverloop."""
    head = text[:3000]
    m = re.search(r"\b(procesverloop|de procedure|het geding|verloop van de procedure|de feiten)\b", head[300:], re.I)
    return head[:300 + m.start()] if m else head


def count_terms(text, terms):
    low = text.lower()
    return {t: n for t in terms if (n := len(re.findall(r"\b" + re.escape(t), low)))}


ENERGY_WORDS = re.compile(
    r"\b(energie\w*|elektriciteit\w*|elektra|stroom\w*|aardgas\w*|warmte\w*|netbeheer\w*|"
    r"gas(levering|aansluiting|net|verbruik|winning|leverancier|prijs|contract|meter)?)\b")
# Huur-, VvE- en parkzaken noemen vaak energiekosten zonder over energierecht te gaan.
RENTAL = re.compile(r"\b(huur\w*|verhuur\w*|servicekosten|nutskosten|nutsvoorziening\w*|vve|vereniging van eigenaars|"
                    r"recreatiepark|bungalowpark|vakantiepark)\b", re.I)


def signals(r):
    low = r["text"].lower()
    summary = r["summary"].lower()
    head = header(r["text"])
    return {
        "subject": [x.lower() for x in r["subject"]],
        "laws": [law for law in LAWS if re.search(r"\b" + re.escape(law), low)],
        "parties": sorted({m.group(0).strip() for m in KNOWN_COMPANIES.finditer(head)}),
        "other_parties": sorted({m.group(0).strip() for m in OTHER_COMPANIES.finditer(head)}),
        "summary_terms": {**count_terms(summary, TERMS + LAWS),
                          **{m.group(0).lower(): 1 for m in KNOWN_COMPANIES.finditer(r["summary"])}},
        "text_terms": count_terms(low, TERMS),
        "energy_words": len(ENERGY_WORDS.findall(low)),
        "rental": bool(RENTAL.search(summary)),
        "hennep": [w for w in EXCLUDE if w in low or w in summary],
    }


def relevance(sig):
    """Geeft (reden, toelichting) als een uitspraak relevant is, anders None.
    - wet: de tekst verwijst naar energiewetgeving;
    - samenvatting: de samenvatting noemt een energiebegrip of energiebedrijf;
    - partij: een energiebedrijf is partij en de zaak gaat over energie (de tekst noemt energie vaker dan terloops);
    - tekst: de tekst noemt vijf keer of vaker een kernbegrip, en het is geen huur- of VvE-zaak.
    Partij en tekst tellen niet in insolventie-, arbeids- en familiezaken."""
    if sig["hennep"]:
        return None
    if sig["laws"]:
        return "wet", ", ".join(sig["laws"][:3])
    if sig["summary_terms"]:
        return "samenvatting", ", ".join(list(sig["summary_terms"])[:3])
    if any(s.endswith(x) for s in sig["subject"] for x in NO_PARTY_SUBJECTS):
        return None
    about_energy = sig["energy_words"] >= 3
    if about_energy and sig["parties"]:
        return "partij", sig["parties"][0]
    if about_energy and sig["other_parties"] and sig["text_terms"]:
        return "partij", sig["other_parties"][0]
    core = {t: n for t, n in sig["text_terms"].items() if t in CORE}
    if sum(core.values()) >= CORE_THRESHOLD and not sig["rental"]:
        return "tekst", ", ".join(f"{t} ({n}x)" for t, n in sorted(core.items(), key=lambda x: -x[1])[:3])
    return None


def to_item(r, reason, first_seen):
    """Een uitspraak in de vorm van de databank (zie fetch.py). reason = (grond, toelichting)."""
    summary = r["summary"]
    first = summary.rstrip(".;")
    if len(first) > 140:
        first = first[:140].rsplit(" ", 1)[0] + "…"
    title = f"{r['instantie'] or 'Rechtspraak'}: {first} ({r['ecli']})" if first else f"{r['instantie']}, {r['ecli']}"
    return {
        "title": title,
        "url": DETAILS.format(r["ecli"]),
        "date": f"{r['datum']}T00:00:00+00:00",
        "date_checked": True,
        "summary": summary[:400],
        "source": "civiel",
        "first_seen": first_seen,
        "grond": reason[0],
        "toelichting": reason[1],
    }


def check(ecli, first_seen):
    """Haalt de uitspraak op en geeft (item of None, uitspraakjaar)."""
    r = fetch_ruling(ecli)
    if not r["datum"]:
        return None, None
    reason = relevance(signals(r))
    seen = first_seen or f"{r['gepubliceerd'] or r['datum']}T00:00:00+00:00"
    return (to_item(r, reason, seen) if reason else None), int(r["datum"][:4])


def load_year(year):
    path = ARCHIVE / f"{year}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"jaar": year, "maanden": [], "mislukt": [], "items": []}


def save_year(data):
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    data["items"].sort(key=lambda i: i["date"], reverse=True)
    data["mislukt"] = sorted(set(data["mislukt"]))
    (ARCHIVE / f"{data['jaar']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_archive():
    """Alle relevante civiele uitspraken uit het archief."""
    items = []
    for path in sorted(ARCHIVE.glob("[0-9][0-9][0-9][0-9].json")):
        items += json.loads(path.read_text(encoding="utf-8"))["items"]
    return items


def archive_year(year, on_month=None):
    """Bouwt het archief van één jaar op, maand voor maand (hervat waar het gebleven was)."""
    data = load_year(year)
    today = date.today()
    for month in range(1, 13):
        key = f"{year}-{month:02d}"
        if key in data["maanden"] or date(year, month, 1) > today:
            continue
        end = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).isoformat()
        entries = search(date=(f"{key}-01", end))
        t0, found = time.time(), 0
        known = {i["url"] for i in data["items"]}
        for e in entries:
            try:
                item, _ = check(e["ecli"], None)
            except Exception as ex:  # één onbereikbare uitspraak mag de rest niet stoppen
                data["mislukt"].append(e["ecli"])
                print(f"  FOUT {e['ecli']}: {type(ex).__name__}: {ex}", flush=True)
                continue
            if item and item["url"] not in known:
                data["items"].append(item)
                known.add(item["url"])
                found += 1
        if date(year, month, 1) + timedelta(days=40) < today:  # lopende maanden later opnieuw
            data["maanden"].append(key)
        save_year(data)
        print(f"{key}: {len(entries)} uitspraken, {found} relevant ({time.time() - t0:.0f}s)", flush=True)
        if on_month:
            on_month(key)
    return data


def retry_failed(year):
    data = load_year(year)
    todo, data["mislukt"] = data["mislukt"], []
    known = {i["url"] for i in data["items"]}
    for ecli in todo:
        try:
            item, _ = check(ecli, None)
        except Exception:
            data["mislukt"].append(ecli)
            continue
        if item and item["url"] not in known:
            data["items"].append(item)
    save_year(data)


def reassess(year):
    """Past de huidige selectie opnieuw toe op de uitspraken die al in het archief staan.
    Nodig als de selectie strenger is gemaakt; voor een ruimere selectie moet het jaar opnieuw worden doorzocht."""
    data = load_year(year)
    kept, dropped = [], 0
    for item in data["items"]:
        ecli = item["url"].split("id=")[-1]
        try:
            r = fetch_ruling(ecli)
        except Exception:
            kept.append(item)  # niet bereikbaar: laten staan
            continue
        reason = relevance(signals(r))
        if reason:
            new = to_item(r, reason, item["first_seen"])
            kept.append(new)
        else:
            dropped += 1
            print(f"  vervalt: {ecli} {item['summary'][:100]}", flush=True)
    data["items"] = kept
    save_year(data)
    print(f"{year}: {len(kept)} blijven, {dropped} vervallen", flush=True)


def update(now=None):
    """Dagelijks: controleert de civiele uitspraken die sinds de vorige keer zijn gepubliceerd of gewijzigd.
    Er wordt een paar uur overlap genomen; een uitspraak die al in het archief staat, wordt alleen bijgewerkt."""
    now = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    since = state.get("gewijzigd_sinds") or (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
    query_from = (datetime.fromisoformat(since) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
    entries = sorted(search(modified=(query_from,)), key=lambda e: e["updated"])[:MAX_PER_RUN]
    years, added, removed = {}, 0, 0
    last = since
    for e in entries:
        try:
            item, year = check(e["ecli"], now)
        except Exception as ex:
            print(f"  FOUT {e['ecli']}: {type(ex).__name__}: {ex}")
            break  # later opnieuw vanaf deze uitspraak
        last = max(last, e["updated"][:19])
        if year is None or year < START_YEAR:
            continue
        data = years.setdefault(year, load_year(year))
        url = DETAILS.format(e["ecli"])
        old = next((i for i in data["items"] if i["url"] == url), None)
        if old:
            data["items"].remove(old)
            if item:
                item["first_seen"] = old["first_seen"]
            else:
                removed += 1
        if item:
            data["items"].append(item)
            added += not old
    for data in years.values():
        save_year(data)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"gewijzigd_sinds": last}, indent=1) + "\n", encoding="utf-8")
    return f"  {len(entries)} gewijzigde civiele uitspraken gecontroleerd, {added} nieuw relevant, {removed} vervallen"


if __name__ == "__main__":
    # python scripts/civiel.py archief 2025        (archief van één jaar opbouwen)
    # python scripts/civiel.py herbeoordeel 2025   (selectie opnieuw toepassen op het archief)
    if len(sys.argv) >= 3 and sys.argv[1] == "herbeoordeel":
        reassess(int(sys.argv[2]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "archief":
        year = int(sys.argv[2])
        if not STATE.exists():  # vanaf nu houdt de dagelijkse run de nieuwe uitspraken bij
            ARCHIVE.mkdir(parents=True, exist_ok=True)
            start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            STATE.write_text(json.dumps({"gewijzigd_sinds": start}, indent=1) + "\n", encoding="utf-8")
        commit = None
        if "--commit" in sys.argv:  # tussentijds opslaan in git, zodat een afgebroken run kan hervatten
            import subprocess

            def commit(key):
                subprocess.run(["git", "add", str(ARCHIVE)], check=True)
                if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode:
                    subprocess.run(["git", "commit", "-q", "-m", f"Archief civiele uitspraken {key}"], check=True)
                    for _ in range(3):
                        if subprocess.run(["git", "pull", "-q", "--rebase"]).returncode == 0 and \
                                subprocess.run(["git", "push", "-q"]).returncode == 0:
                            break
                        time.sleep(5)
        archive_year(year, on_month=commit)
        retry_failed(year)
        if commit:
            commit(f"{year} (herhaalde pogingen)")
    else:
        print(__doc__)
