# Tijdelijk: juiste adressen voor wetten en kapotte vaste links
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
get() { curl -sL -A "$UA" -H "Accept-Language: nl,en;q=0.8" --max-time 40 "$@"; }

for b in BWBR0050714 BWBR0052212 BWBR0033729; do
  echo "################ $b"
  get -o w.html -w "status %{http_code} final %{url_effective}\n" "https://wetten.overheid.nl/$b"
  grep -oE '<title>[^<]*' w.html
  grep -oiE '(Geldend van|Regeling vervallen|Vervallen per|nog niet in werking|inwerkingtreding)[^<]{0,140}' w.html | sort | uniq -c | sort -rn | head -12
  get -o i.html "https://wetten.overheid.nl/$b/informatie"
  python3 - <<'PY'
import re, html
t = open("i.html", errors="replace").read()
t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t)).split())
for key in ["Citeertitel", "Inwerkingtreding", "inwerkingtreding", "Staatsblad", "Officiële titel", "Wijzigingenoverzicht"]:
    for m in re.finditer(key, t):
        print("  ..", t[max(0, m.start()-60):m.start()+260])
        break
PY
done

echo "################ Wcw: welke artikelen gelden nu"
get -o wcw.html "https://wetten.overheid.nl/BWBR0052212"
python3 - <<'PY'
import re, html
t = open("wcw.html", errors="replace").read()
t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t)).split())
print(len(t))
print(t[:1500])
for m in re.finditer(r"(treedt in werking|in werking|Vervallen|nog niet)", t):
    print("  ..", t[max(0, m.start()-150):m.start()+200])
PY

echo "################ officielebekendmakingen Wcw"
get -o ob.html "https://zoek.officielebekendmakingen.nl/resultaten?q=(c.product-area==%22officielepublicaties%22)and(dt.type==%22Staatsblad%22)and(cql.textAndIndexes=%22Wet%20collectieve%20warmte%22)&zv=Wet+collectieve+warmte&col=Staatsblad"
grep -oE 'stb-20[0-9]{2}-[0-9]+[^"]*"[^>]*>[^<]{0,160}' ob.html | head -15

echo "################ ACM links"
get -o acm.html "https://www.acm.nl/nl/energie"
grep -oE 'href="[^"]*"[^>]*>[^<]{0,80}' acm.html | grep -iE 'tarie|code|methode|netbeheer|regulering|elektriciteit|gas' | sort -u | head -40
for u in https://www.acm.nl/nl/energie/elektriciteit-en-gas https://www.acm.nl/nl/energie/netbeheer https://www.acm.nl/nl/energie/elektriciteit-en-gas/netbeheer; do
  get -o x.html -w "%{http_code} %{url_effective}\n" "$u"; grep -oE '<title>[^<]*' x.html
done
get -o acmsm.xml "https://www.acm.nl/sitemap.xml"; echo "sitemap bytes $(wc -c < acmsm.xml)"
grep -oE '<loc>[^<]*' acmsm.xml | head -3
grep -oE '<loc>[^<]*(tarie|codes|methodebesluit|netcode)[^<]*' acmsm.xml | head -30

echo "################ ACER REMIT"
get -o acer.html "https://www.acer.europa.eu/"
grep -oE 'href="[^"]*remit[^"]*"' acer.html | sort -u | head -20
for u in https://www.acer.europa.eu/remit-0 https://www.acer.europa.eu/market-monitoring/remit https://www.acer.europa.eu/remit/about-remit; do
  get -o x.html -w "%{http_code} %{url_effective}\n" "$u"; grep -oE '<title>[^<]*' x.html
done

echo "################ EUR-Lex"
for c in 32019L0944 32019R0943 32011R1227 32018L2001; do
  get -o e.html -w "%{http_code} %{url_effective} %{size_download}\n" -H "Accept: text/html,application/xhtml+xml" "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:$c"
  grep -oE '<title>[^<]*' e.html; grep -oiE 'challenge|captcha|awswaf' e.html | sort -u | head -3
  get -o e2.html -w "  eli/publications: %{http_code} %{url_effective} %{size_download}\n" "https://publications.europa.eu/resource/celex/$c"
done
