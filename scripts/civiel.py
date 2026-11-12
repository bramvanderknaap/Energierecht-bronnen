"""Civiele uitspraken over energierecht uit de open data van rechtspraak.nl.

De zoekfunctie van rechtspraak.nl geeft alleen het ECLI-nummer en de samenvatting (inhoudsindicatie).
Daarom wordt van elke civiele uitspraak de volledige tekst opgehaald en daarin gezocht naar:
- verwijzingen naar energiewetgeving (Elektriciteitswet 1998, Gaswet, Energiewet, Warmtewet, ...),
- energiebedrijven als procespartij (leveranciers, netbeheerders, producenten),
- energiebegrippen in de samenvatting of herhaaldelijk in de tekst.
Zaken over hennepteelt vallen af."""
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

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
COMPANY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in COMPANIES) + r")\b"
    r"|[\w&'.-]*(energie|energy|netbeheer|windpark|zonnepark|solar)[\w&'.-]*(\s+[\w&'.-]+){0,3}\s+(b\.v\.|n\.v\.|u\.a\.)",
    re.I)
# Energiebegrippen: tellen mee in de samenvatting, of als ze vaak in de tekst staan.
TERMS = [
    "energieleverancier", "energiebedrijf", "energiecontract", "energielevering", "energierekening",
    "energieprijs", "energietarie", "leveringsovereenkomst energie", "levering van elektriciteit",
    "levering van gas", "levering van energie", "elektra en gas", "gas en elektra", "stroom en gas",
    "netbeheerder", "netaansluiting", "aansluit- en transportovereenkomst", "transportcapaciteit",
    "transportvermogen", "netcongestie", "stroomstoring", "gasaansluiting", "elektriciteitsaansluiting",
    "warmtenet", "warmtelevering", "warmteleverancier", "stadsverwarming", "zonnepark", "zonnepane",
    "zonne-energie", "windturbine", "windpark", "windmolen", "laadpa", "laadpunt", "terugleverkosten",
    "terugleververgoeding", "salderingsregeling", "energieopslag", "biogas", "kernenergie", "gaswinning",
    "aardbevingsschade", "mijnbouwschade", "mijnbouw", "energietransitie", "warmtekrachtkoppeling",
]
EXCLUDE = ["hennep", "cannabis", "growshop", "wietplant", "wietteelt", "wietkwekerij"]
TERM_THRESHOLD = 3


def download(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


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
    r = {"ecli": ecli, "instantie": "", "datum": "", "subject": [], "summary": "", "text": ""}
    for el in root.iter():
        name = local(el.tag)
        if name == "creator" and not r["instantie"]:
            r["instantie"] = (el.text or "").strip()
        elif name == "date" and "Uitspraakdatum" in str(el.attrib.values()):
            r["datum"] = (el.text or "").strip()
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


def signals(r):
    low = r["text"].lower()
    summary = r["summary"].lower()
    parties = sorted({m.group(0).strip() for m in COMPANY_PATTERN.finditer(header(r["text"]))})
    return {
        "laws": [law for law in LAWS if re.search(r"\b" + re.escape(law), low)],
        "parties": parties,
        "summary_terms": count_terms(summary, TERMS + LAWS + COMPANIES),
        "text_terms": count_terms(low, TERMS),
        "hennep": [w for w in EXCLUDE if w in low or w in summary],
    }


def relevance(sig):
    """Geeft de reden waarom een uitspraak relevant is, of None."""
    if sig["hennep"]:
        return None
    if sig["laws"]:
        return "wet"
    if sig["parties"]:
        return "partij"
    if sig["summary_terms"]:
        return "samenvatting"
    if sum(sig["text_terms"].values()) >= TERM_THRESHOLD:
        return "tekst"
    return None
