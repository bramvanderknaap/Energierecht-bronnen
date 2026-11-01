# Energierecht Bronnen

Een website die publicaties en rechtsbronnen over energierecht op één plek verzamelt:
ACM, ACER, de Europese Commissie (DG Energie), CEER, de Rijksoverheid, uitspraken van het CBb en arresten van het Hof van Justitie van de EU.

## Hoe werkt het?

- `sources.json` – de lijst met bronnen, hun nieuwsfeeds en vaste links. Een bron toevoegen of aanpassen doe je hier.
- `scripts/fetch.py` – haalt de nieuwste publicaties op en zet ze in `data/items.json`.
- `.github/workflows/update.yml` – laat GitHub dit script elke ochtend automatisch draaien.
- `index.html`, `style.css`, `app.js` – de website zelf, gepubliceerd via GitHub Pages.
- `assets/` – het logo.

## Arresten van het Hof van Justitie

De arresten komen uit de databank van het Publicatiebureau van de EU (de SPARQL-dienst van Cellar), niet van een nieuwsfeed.
Een arrest van het Hof of het Gerecht sinds 2019 telt als relevant als het onder het onderwerp Energie is ingedeeld, als het verwijst
naar een van de energierichtlijnen of -verordeningen in `acts`, of als de Nederlandse titel een van de `title_words` bevat.
Zaken die in de eerste plaats over belastingen gaan (accijns, btw, energiebelasting) vallen af via `exclude_title`.
Die lijsten staan bij de bron `hvjeu` in `sources.json`. Deze bron bewaart tot 400 arresten (`max_items`), de andere bronnen 150 items.

## Huisstijl

Naar het voorbeeld van Wintervlam Advocaten: bovenaan een blauwe lucht met grote, dunne witte koppen, daaronder wit met diep petrol (#193B43) voor tekst en knoppen, licht zeegroen (#D1E6E6) voor lijnen en kleine labels in hoofdletters, en een petrol voet. Rechte hoeken. Koppen in Libre Franklin Light, lopende tekst in Inter. Alleen een licht thema, geen animatie. Teksten blijven zakelijk en kort. Kleuren staan als variabelen bovenaan `style.css`.
