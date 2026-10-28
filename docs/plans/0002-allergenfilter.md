# Plan 0002 – Allergen- og diettfilter på menyen

**Status:** Godkjent
**Ansvarlig:** jonasloland
**Interessent/behov:** Kunder med allergier/dietter som vil se bare retter de kan bestille.

## Mål
Avkrysningsbokser over menyen: «Skjul retter med …» (allergener) og «Vis kun …» (dietter).
Filteret ligger i URL-en (GET), f.eks. `/?uten=gluten&uten=melk&kun=vegan`, slik at det kan
deles/bokmerkes og kombineres med `event`.

## Berørte filer
- models: `app/models/services.py` – ny ren funksjon `filter_dishes(dishes, exclude_allergens, require_diets)`
- controllers: `app/controllers/shop.py` (`menu`) – leser `uten`/`kun`, forkaster ukjente nøkler, kaller filteret
- templates: `app/templates/shop/menu.html` – GET-skjema med `checkbox_group`, tabs beholder filteret
- tests: `tests/test_models.py` (filterfunksjonen), `tests/test_routes.py` (`/?uten=gluten`)

## Steg
1. `filter_dishes`: skjul retter som har *minst ett* valgt allergen; behold kun retter som har
   *alle* valgte dietter. Tomme valg = ingen filtrering.
2. Controller validerer mot `ALLERGENS`/`DIETS` og sender valgene til malen.
3. Mal: skjema (GET, ingen CSRF nødvendig) med skjult `event`-felt, «Bruk filter» og «Nullstill».
4. Tester.

## Verifisering
- Tester: enhetstest for `filter_dishes` (allergen, diett, kombinasjon, tomt filter) og rutetest
  for `/?uten=gluten`. `python -m pytest -q` grønn.
- Manuell sjekk: kryss av «Gluten» på menyen og se at glutenretter forsvinner.

## Risiko / åpne spørsmål
- Filteret stoler på at allergenmerkingen på rettene er korrekt – det er en hjelp, ikke en garanti.
