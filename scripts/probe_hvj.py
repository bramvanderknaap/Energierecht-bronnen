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

q("predicaten C-718/18", """
SELECT DISTINCT ?p ?o WHERE {
  ?w cdm:resource_legal_id_celex ?c . FILTER(STR(?c)="62018CJ0718")
  ?w ?p ?o . FILTER(!isBlank(?o))
} LIMIT 120""", show=120)

q("energie-arresten HvJ sinds 2018", """
SELECT DISTINCT ?celex ?date WHERE {
  ?w cdm:resource_legal_is_about_subject-matter <http://publications.europa.eu/resource/authority/subject-matter/ENER> ;
     cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  FILTER(REGEX(STR(?celex), "^6[0-9]{4}CJ"))
  FILTER(?date >= "2018-01-01"^^xsd:date)
} ORDER BY DESC(?date) LIMIT 60""", show=60)

q("titels NL van recente energie-arresten", """
SELECT DISTINCT ?celex ?date ?title WHERE {
  ?w cdm:resource_legal_is_about_subject-matter <http://publications.europa.eu/resource/authority/subject-matter/ENER> ;
     cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
  FILTER(REGEX(STR(?celex), "^6[0-9]{4}CJ"))
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/NLD> ; cdm:expression_title ?title .
} ORDER BY DESC(?date) LIMIT 8""", show=8)
