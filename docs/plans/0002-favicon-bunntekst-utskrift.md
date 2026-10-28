# Plan 0002 – Favicon, bunntekst, utskrift av kjøkkenvisning og interessenter

**Status:** Godkjent
**Ansvarlig:** Trine Kulseth
**Interessent/behov:** Kunder (kontaktinfo og gjenkjennelig fane), kokker (papirutskrift der
allergier synes også på svart-hvitt-skriver), teamet (oversikt over interessenter og funksjoner).

## Mål
- Favicon (tallerken med skje) i alle faner.
- Bunntekst med telefon, e-post og åpningstider på alle sider (syntetiske data).
- `/admin/kjokken` kan skrives ut: bare ordrene, allergier uthevet med fet skrift, ramme og ⚠.
- `docs/interessenter.md` som kobler interessenter til eksisterende ruter.

## Berørte filer
- models: ingen
- controllers: ingen
- templates: `base.html` (favicon-lenke, bunntekst), `admin/kitchen.html` («Skriv ut»-knapp)
- static: `favicon.svg` (ny), `css/style.css` (bunntekst + `@media print`)
- tests: `tests/test_routes.py`
- docs: `docs/interessenter.md`

## Steg
1. Favicon + bunntekst + test.
2. `@media print` i `style.css` og «Skriv ut»-knapp (`window.print()`, klasse `no-print`) + test.
3. Interessentdokument basert på rutene i `controllers/`.

## Verifisering
- Tester: favicon-lenke og bunntekst på `/`; «Skriv ut» på `/admin/kjokken` (innlogget admin).
- Manuell sjekk: utskriftsforhåndsvisning av `/admin/kjokken` viser bare ordrekort i svart/hvitt
  med allergier i fet skrift, ramme og ⚠; meny, knapper og bunntekst er skjult.

## Risiko / åpne spørsmål
- Ingen egne roller for kokk/daglig leder – de bruker admin-innloggingen.
- Allergiutheving på papir dekker allergener på retter og gjestegruppenotater, ikke fritekst ellers.
