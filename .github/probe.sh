# Tijdelijk: juiste ACM-pagina's voor tarieven en codes
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
get() { curl -sL -A "$UA" -H "Accept-Language: nl,en;q=0.8" --max-time 40 "$@"; }
for u in https://www.acm.nl/nl/energie/elektriciteit-en-gas https://www.acm.nl/nl/energie/elektriciteit-en-gas/netbeheer; do
  echo "################ $u"
  get -o p.html "$u"
  grep -oE 'href="/nl/[^"]*"[^>]*>[^<]{0,90}' p.html | grep -vE 'zoeken|contact|over-de-acm|nieuws' | sort -u | head -60
done
echo "################ sitemap"
for n in 1 2 3 4 5 6; do get "https://www.acm.nl/sitemap.xml?page=$n"; done | grep -oE '<loc>[^<]*' | sed 's/<loc>//' > sm.txt
wc -l sm.txt
grep -iE '/nl/energie/' sm.txt | grep -iE 'tarie|code|methode|regulering|x-factor' | grep -vE '/nl/publicaties/' | head -40
for u in $(grep -iE '/nl/energie/' sm.txt | grep -iE 'tarie|codes|methode' | grep -vE '/nl/publicaties/' | head -12); do
  get -o x.html -w "%{http_code} $u | " "$u"; grep -oE '<title>[^<]*' x.html | head -1
done
