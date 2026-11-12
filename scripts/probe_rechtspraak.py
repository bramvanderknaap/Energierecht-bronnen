"""Tijdelijke verkenning van de open data van rechtspraak.nl (wordt niet samengevoegd).
Vergelijkt voor één maand: selectie op samenvatting versus selectie op volledige tekst."""
import json, re, sys, time, urllib.request
import xml.etree.ElementTree as ET
from collections import Counter

sys.path.insert(0, "scripts")
import fetch

H = {"User-Agent": "Mozilla/5.0 (compatible; energierecht-bronnen/1.0; +https://github.com/)"}
BASE = "https://data.rechtspraak.nl/uitspraken/zoeken?subject=http://psi.rechtspraak.nl/rechtsgebied%23civielRecht&type=Uitspraak&return=DOC"
MONTH = ("2025-10-01", "2025-10-31")


def get(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


for u in ["https://uitspraken.rechtspraak.nl/robots.txt", "https://data.rechtspraak.nl/robots.txt"]:
    try:
        print(u, "\n", get(u).decode("utf-8", "replace")[:800])
    except Exception as e:
        print(u, "FOUT", e)

entries = []
for n in range(20):
    raw = get(f"{BASE}&date={MONTH[0]}&date={MONTH[1]}&max=1000&from={n*1000}")
    root = ET.fromstring(raw)
    page = []
    for el in root:
        if fetch.local(el.tag) != "entry":
            continue
        title = fetch.child_text(el, "title")
        summ = fetch.strip_html(fetch.child_text(el, "summary"))
        page.append({"title": title, "summary": summ, "ecli": title.split(",")[0].strip()})
    entries += page
    time.sleep(1)
    if len(page) < 1000:
        break

src = next(s for s in json.load(open("sources.json")) if s["id"] == "civiel")
with_summary = [e for e in entries if len(e["summary"]) > 5]
print(f"\nMaand {MONTH}: {len(entries)} civiele ECLI's, {len(with_summary)} met samenvatting")
print("lengte samenvatting > 400 tekens:", sum(len(e["summary"]) > 400 for e in with_summary))
summ_hits = {e["ecli"] for e in with_summary if fetch.is_relevant(e, src)}
print("relevant op samenvatting (huidige methode, hele samenvatting):", len(summ_hits))

LAWS = ["Elektriciteitswet", "Gaswet", "Energiewet", "Warmtewet", "Mijnbouwwet", "Wet collectieve warmte",
        "Wet windenergie op zee", "Netcode", "Tarievencode", "Begrippencode", "Meetcode", "Informatiecode",
        "Regeling afnemers", "Besluit factuur", "Wet voortgang energietransitie", "Besluit leveringszekerheid",
        "Wet implementatie EU-richtlijnen energie", "Warmtebesluit", "Warmteregeling", "Mijnbouwbesluit",
        "Tijdelijke wet Groningen", "Besluit aanleg energie", "Wet bevordering duurzame", "Wet opslag duurzame"]
TERMS = ["netbeheerder", "energieleverancier", "aansluit- en transportovereenkomst", "transportcapaciteit",
         "netcongestie", "warmtenet", "zonnepark", "windpark", "windturbine", "gaswinning", "aardbevingsschade",
         "laadpaal", "energiecontract", "leveringsovereenkomst", "elektriciteit", "aardgas", "netaansluiting"]
EXCL = ["hennep", "cannabis", "growshop", "wietplant", "wietteelt"]

# Steekproef zonder samenvatting: hebben die tekst?
no_summary = [e for e in entries if len(e["summary"]) <= 5][:15]
withtext = 0
for e in no_summary:
    t = get(f"https://data.rechtspraak.nl/uitspraken/content?id={e['ecli']}").decode("utf-8", "replace")
    withtext += "<uitspraak" in t
    time.sleep(0.3)
print(f"steekproef zonder samenvatting: {withtext} van {len(no_summary)} hebben toch tekst")

t0 = time.time()
law_hits, rows, sizes = {}, [], []
for k, e in enumerate(with_summary):
    try:
        t = get(f"https://data.rechtspraak.nl/uitspraken/content?id={e['ecli']}").decode("utf-8", "replace")
    except Exception as ex:
        print("FOUT", e["ecli"], ex)
        continue
    sizes.append(len(t))
    m = re.search(r"<uitspraak.*", t, re.S)
    body = fetch.strip_html(m[0]) if m else ""
    low = body.lower()
    laws = [l for l in LAWS if l.lower() in low]
    terms = Counter({w: low.count(w) for w in TERMS if w in low})
    excl = [w for w in EXCL if w in low]
    subj = re.findall(r'rechtsgebied#([A-Za-z_]+)', t)
    if laws or sum(terms.values()) >= 5:
        rows.append((e, laws, terms, excl, subj))
    time.sleep(0.25)
print(f"\nvolledige tekst opgehaald: {len(sizes)} in {time.time()-t0:.0f}s, gem. {sum(sizes)//max(len(sizes),1)} bytes")

law_set = {e["ecli"] for e, laws, terms, excl, subj in rows if laws and not excl}
print("noemt een energiewet (zonder hennep):", len(law_set))
print("daarvan niet gevonden op samenvatting:", len(law_set - summ_hits))
print("op samenvatting gevonden maar geen energiewet in tekst:", len(summ_hits - law_set))
print("\n--- alle uitspraken met energiewet of >=5 energietermen ---")
for e, laws, terms, excl, subj in rows:
    flag = ("S" if e["ecli"] in summ_hits else "-") + ("W" if laws else "-") + ("H" if excl else "-")
    print(flag, e["ecli"], "|", ",".join(laws)[:80], "|", dict(terms.most_common(4)), "|", subj[:1], "|", e["summary"][:160])
