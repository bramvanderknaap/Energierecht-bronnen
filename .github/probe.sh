# Tijdelijk: verkennen van CBb-metadata en wetlinks
UA="Mozilla/5.0 (compatible; energierecht-bronnen/1.0)"
get() { curl -sL -A "$UA" --max-time 40 "$@"; }

echo "################ CBb Atom feed (eerste entries)"
get "https://data.rechtspraak.nl/uitspraken/zoeken?creator=http://standaarden.overheid.nl/owms/terms/College_van_Beroep_voor_het_bedrijfsleven&max=4&sort=DESC&return=DOC" | head -c 3500; echo

for e in ECLI:NL:CBB:2026:445 ECLI:NL:CBB:2026:299 ECLI:NL:CBB:2026:111 ECLI:NL:CBB:2025:552 ECLI:NL:CBB:2026:282; do
  echo "################ META $e"
  get "https://data.rechtspraak.nl/uitspraken/content?id=$e&return=META" > meta.xml
  echo "bytes: $(wc -c < meta.xml)"
  grep -oE '<dcterms:(date|issued|modified)[^>]*>[^<]*' meta.xml
  grep -oE '<(dcterms:)?(title|subject|procedure)[^>]*>[^<]{0,120}' meta.xml | head -6
done

echo "################ zoeken met date-filter (uitspraakdatum)"
get "https://data.rechtspraak.nl/uitspraken/zoeken?creator=http://standaarden.overheid.nl/owms/terms/College_van_Beroep_voor_het_bedrijfsleven&date=2026-09-01&date=2026-10-13&max=5&return=DOC" | grep -oE '<(title|updated)>[^<]*' | head -12

echo "################ wetten.overheid.nl zoeken"
for t in Energiewet "Wet collectieve warmte" "Wet collectieve warmtevoorziening" Warmtewet Elektriciteitswet Gaswet; do
  echo "== zoek: $t"
  q=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$t")
  get "https://wetten.overheid.nl/zoeken/zoekresultaat/titelf/1/titel/$q/te/1/geldigheidsdatum/13-10-2026" > z.html
  echo "bytes: $(wc -c < z.html)"
  grep -oE 'BWBR[0-9]{7}[^"]*"[^>]*>[^<]{0,150}' z.html | head -10
  get "https://wetten.overheid.nl/zoeken?titel=$q" > z2.html
  echo "bytes2: $(wc -c < z2.html)"
  grep -oE 'BWBR[0-9]{7}[^"]*"[^>]*>[^<]{0,150}' z2.html | head -10
done

echo "################ SRU BWB"
for q in 'overheidbwb.titel="Energiewet"' 'dcterms.title="Energiewet"' 'overheidbwb.titel any "collectieve warmte"' 'dcterms.title any "collectieve warmte"'; do
  echo "== $q"
  enc=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$q")
  get "https://zoekservice.overheid.nl/sru/Search?x-connection=BWB&operation=searchRetrieve&version=1.2&maximumRecords=10&query=$enc" > sru.xml
  echo "bytes: $(wc -c < sru.xml)"
  grep -oE '<(dcterms:identifier|dcterms:title|overheidbwb:titel|overheidbwb:geldigheidsperiode_startdatum|overheidbwb:geldigheidsperiode_einddatum|overheidbwb:inwerkingtredingsdatum|overheidbwb:zichtdatum|diagnostic:message|message)[^>]*>[^<]{0,150}' sru.xml | head -40
done

echo "################ huidige wetlinks"
for u in https://wetten.overheid.nl/BWBR0009755 https://wetten.overheid.nl/BWBR0011440 https://wetten.overheid.nl/BWBR0033729; do
  echo "== $u"
  get -o w.html -w "status %{http_code} final %{url_effective}\n" "$u"
  grep -oE '<title>[^<]*' w.html
  grep -oiE '.{0,80}(vervallen|niet meer geldig|geldend van|geldig van|Geldend van)[^<]{0,120}' w.html | head -5
done

echo "################ alle vaste links"
python3 - <<'PY'
import json, subprocess
for s in json.load(open("sources.json")):
    for l in s.get("links", []):
        out = subprocess.run(["curl","-sL","-A","Mozilla/5.0","--max-time","40","-o","p.html","-w","%{http_code} %{url_effective}", l["url"]], capture_output=True, text=True).stdout
        import re
        try: t = re.search(r"<title[^>]*>([^<]*)", open("p.html", errors="replace").read()); t = " ".join(t[1].split())[:120] if t else ""
        except Exception: t = ""
        print(f"{s['id']:12} {out} | {l['title']} | {t}")
PY
