# Energierecht Bronnen

Een website die publicaties en rechtsbronnen over energierecht op één plek verzamelt:
ACM, ACER, de Europese Commissie (DG Energie), CEER, de Rijksoverheid en uitspraken van het CBb.

## Hoe werkt het?

- `sources.json` – de lijst met bronnen, hun nieuwsfeeds en vaste links. Een bron toevoegen of aanpassen doe je hier.
- `scripts/fetch.py` – haalt de nieuwste publicaties op en zet ze in `data/items.json`.
- `.github/workflows/update.yml` – laat GitHub dit script elke ochtend automatisch draaien.
- `index.html`, `style.css`, `app.js` – de website zelf, gepubliceerd via GitHub Pages.
- `assets/` – de tekeningen van de huisstijl: het landschap met zonnepark, windturbines en 380 kV-lijn (`landschap-breed.svg` voor brede schermen, `landschap-smal.svg` voor telefoons) en het logo.

## Huisstijl

"Noordzeedaglicht", rustige versie: alleen een licht thema, een lichte Noordzeelucht met een stille lijntekening van zonnepark, windturbines en hoogspanning achter de kop, verder wit met donkerblauw voor tekst en knoppen. Geen animatie. Teksten blijven zakelijk en kort. Kleuren staan als variabelen bovenaan `style.css`.
