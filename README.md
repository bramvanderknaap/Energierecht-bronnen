# Energierecht Bronnen

Een website die publicaties en rechtsbronnen over energierecht op één plek verzamelt:
ACM, ACER, de Europese Commissie (DG Energie), CEER, de Rijksoverheid en uitspraken van het CBb.

## Hoe werkt het?

- `sources.json` – de lijst met bronnen, hun nieuwsfeeds en vaste links. Een bron toevoegen of aanpassen doe je hier.
- `scripts/fetch.py` – haalt de nieuwste publicaties op en zet ze in `data/items.json`.
- `.github/workflows/update.yml` – laat GitHub dit script elke ochtend automatisch draaien.
- `index.html`, `style.css`, `app.js` – de website zelf, gepubliceerd via GitHub Pages.
- `assets/` – de tekeningen van de huisstijl: het landschap met zonnepark, windturbines en 380 kV-lijn (`landschap-breed.svg` voor brede schermen, `landschap-smal.svg` voor telefoons), het aanzicht onderaan de pagina en het logo.

## Huisstijl

"Noordzeedaglicht": een lichte Noordzeelucht met een lijntekening van het net op de achtergrond, donker netblauw als anker en één accentkleur (spanningsgeel) voor wat leeft of klikbaar is. Er is een licht en een donker thema; de bezoeker kan wisselen met de knop rechtsboven. Kleuren staan als variabelen bovenaan `style.css`. Beweging (draaiende rotoren, stroompuls langs de geleiders) staat stil als de bezoeker minder beweging heeft ingesteld.
