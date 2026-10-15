"""Tijdelijke verkenning: welke gegevens over HvJ-uitspraken geeft de SPARQL-dienst van het Publicatiebureau."""
import json, urllib.parse, urllib.request

EP = "https://publications.europa.eu/webapi/rdf/sparql"
PFX = "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"

def q(name, query, show=25):
    url = EP + "?" + urllib.parse.urlencode({"query": PFX + query, "format": "application/sparql-results+json"})
    req = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json", "User-Agent": "energierecht-bronnen/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            rows = json.load(r)["results"]["bindings"]
    except Exception as e:
        print(f"== {name}: FOUT {type(e).__name__}: {e}"); return
    print(f"== {name}: {len(rows)} rijen")
    for b in rows[:show]:
        print("  " + " | ".join(f"{k}={v['value'][:160]}" for k, v in b.items()))

ACTS = ["32019L0944","32019R0943","32009L0072","32009L0073","32009R0714","32009R0715","32011R1227","32024R1106",
        "32018L2001","32023L2413","32012L0027","32023L1791","32024L1788","32024R1789","32024L1711","32024R1747",
        "32003L0054","32003L0055","32022R1854","32019R0942","32009R0713","32017R1938","32022R0869","32003L0096"]
ACTLIST = ",".join(f'"{a}"' for a in ACTS)

q("nieuwste HvJ/Gerecht-arresten in de database", """
SELECT ?celex ?date WHERE {
  ?w cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date ; cdm:work_has_resource-type <http://publications.europa.eu/resource/authority/resource-type/JUDG> .
  FILTER(?date >= "2026-06-01"^^xsd:date)
} ORDER BY DESC(?date) LIMIT 8""")

q("A: onderwerp ENER sinds 2019 (CJ+TJ), aantal", """
SELECT (COUNT(DISTINCT ?w) AS ?n) WHERE {
  ?w cdm:resource_legal_is_about_subject-matter <http://publications.europa.eu/resource/authority/subject-matter/ENER> ;
     cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  FILTER(REGEX(STR(?celex), "^6[0-9]{4}(CJ|TJ)")) FILTER(?date >= "2019-01-01"^^xsd:date)
}""")

q("B: citeert energiewetgeving sinds 2019 (CJ+TJ), nieuwste", """
SELECT DISTINCT ?celex ?date (GROUP_CONCAT(DISTINCT ?ac; separator=",") AS ?acts) WHERE {
  ?w cdm:work_cites_work ?act ; cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  ?act cdm:resource_legal_id_celex ?ac . FILTER(STR(?ac) IN (""" + ACTLIST + """))
  FILTER(REGEX(STR(?celex), "^6[0-9]{4}(CJ|TJ)")) FILTER(?date >= "2019-01-01"^^xsd:date)
} GROUP BY ?celex ?date ORDER BY DESC(?date) LIMIT 40""", show=40)

q("B: aantal", """
SELECT (COUNT(DISTINCT ?w) AS ?n) WHERE {
  ?w cdm:work_cites_work ?act ; cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  ?act cdm:resource_legal_id_celex ?ac . FILTER(STR(?ac) IN (""" + ACTLIST + """))
  FILTER(REGEX(STR(?celex), "^6[0-9]{4}(CJ|TJ)")) FILTER(?date >= "2019-01-01"^^xsd:date)
}""")

q("C: recente arresten (sinds 2025-07) met energiewoorden in NL-titel", """
SELECT DISTINCT ?celex ?date ?title WHERE {
  ?w cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  FILTER(REGEX(STR(?celex), "^6[0-9]{4}(CJ|TJ)")) FILTER(?date >= "2025-07-01"^^xsd:date)
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/NLD> ; cdm:expression_title ?title .
  FILTER(REGEX(?title, "elektriciteit|aardgas|energie|warmte|waterstof|netbeheer|hernieuwbare", "i"))
} ORDER BY DESC(?date) LIMIT 25""", show=25)

q("interpretatie-predicaat bij prejudiciele zaak C-48/23", """
SELECT DISTINCT ?p ?ac WHERE {
  ?w cdm:resource_legal_id_celex ?c . FILTER(STR(?c)="62023CJ0048")
  ?w ?p ?o . ?o cdm:resource_legal_id_celex ?ac .
} LIMIT 40""", show=40)
