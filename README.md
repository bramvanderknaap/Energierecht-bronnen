# Energierecht Bronnen

Een website die publicaties en rechtsbronnen over energierecht op één plek verzamelt:
ACM, ACER, de Europese Commissie (DG Energie), CEER, de Rijksoverheid, uitspraken van het CBb en de civiele rechter, en arresten van het Hof van Justitie van de EU.

## Hoe werkt het?

- `sources.json` – de lijst met bronnen, hun nieuwsfeeds en vaste links. Een bron toevoegen of aanpassen doe je hier.
- `scripts/fetch.py` – haalt de nieuwste publicaties op en zet ze in `data/items.json`. Maakt ook de RSS-feed `data/feed.xml`.
- `.github/workflows/update.yml` – laat GitHub dit script elke ochtend automatisch draaien.
- `index.html`, `style.css`, `app.js` – de website zelf, gepubliceerd via GitHub Pages.
- `assets/` – de tekeningen van de huisstijl: het landschap met zonnepark, windturbines en 380 kV-lijn (`landschap-breed.svg` voor brede schermen, `landschap-smal.svg` voor telefoons) en het logo.

## Arresten van het Hof van Justitie

De arresten komen uit de databank van het Publicatiebureau van de EU (de SPARQL-dienst van Cellar), niet van een nieuwsfeed.
Een arrest van het Hof of het Gerecht sinds 2019 telt als relevant als het onder het onderwerp Energie is ingedeeld, als het verwijst
naar een van de energierichtlijnen of -verordeningen in `acts`, of als de Nederlandse titel een van de `title_words` bevat.
Zaken die in de eerste plaats over belastingen gaan (accijns, btw, energiebelasting) vallen af via `exclude_title`.
Die lijsten staan bij de bron `hvjeu` in `sources.json`. Deze bron bewaart tot 400 arresten (`max_items`), de andere bronnen 150 items.

## Civiele uitspraken

De bron `civiel` haalt de nieuwste civiele uitspraken op uit de open data van rechtspraak.nl (rechtsgebied civiel recht,
2.000 per dag; de eerste keer 12.000 om verder terug te gaan). Een uitspraak telt als hij een van de `keywords` bevat,
zoals energieleverancier, netbeheerder, netaansluiting of zonnepark. Uitspraken met een van de `exclude_keywords`
(hennep, cannabis, wiet, growshop, oogst) vallen af, zodat de vele zaken over stroomdiefstal bij hennepteelt er niet in staan.

## Filter op soort

Elke bron heeft in `sources.json` een `soort`: Rechtspraak, Toezichthouders of Beleid. Op de website kun je daarop filteren.

## Updatemails

`data/feed.xml` is een RSS-feed met de 60 publicaties die het laatst aan de databank zijn toegevoegd.
Een nieuwsbriefdienst kan daar automatisch periodieke mails van maken. Zo zet je dat aan:

1. Maak een account bij een nieuwsbriefdienst die mails maakt uit een RSS-feed (bijvoorbeeld Mailchimp, Brevo, Laposta of Buttondown).
2. Maak daar een automatische RSS-mail aan met als feed `https://bramvanderknaap.github.io/Energierecht-bronnen/data/feed.xml` en kies hoe vaak hij gaat (bijvoorbeeld wekelijks).
3. Kopieer het adres van de aanmeldpagina die de dienst je geeft.
4. Zet dat adres in `index.html` bij `data-aanmeld-url=""`. Daarna staat er onderaan de website een knop Aanmelden.

Aanmelden, afmelden en het bewaren van e-mailadressen regelt de nieuwsbriefdienst, niet deze website.

## Huisstijl

"Noordzeedaglicht", rustige versie: alleen een licht thema, een lichte Noordzeelucht met een stille lijntekening van zonnepark, windturbines en hoogspanning achter de kop, verder wit met donkerblauw voor tekst en knoppen. Geen animatie. Teksten blijven zakelijk en kort. Kleuren staan als variabelen bovenaan `style.css`.
