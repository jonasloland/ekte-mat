# Plan 0004 – Eksporter bestillinger til CSV

**Status:** Gjennomført
**Ansvarlig:** kristinepriv-ship-it
**Interessent/behov:** Daglig leder / regnskap, som vil fakturere og føre regnskap i Excel (issue #3).

## Mål
Knapp «Last ned CSV» på `/admin/bestillinger` som laster ned de ordrene som vises med gjeldende
filter (status, eventdato fra/til). Kolonner: id, kunde, eventdato, gjester, total, status,
betalingsstatus. Filen skal åpne riktig i Excel og Numbers med æøå.

## Beslutninger
| Tema | Valg | Begrunnelse |
|---|---|---|
| Bibliotek | Pythons innebygde `csv` | Krav i issue; ingen nye avhengigheter |
| Hvor logikken bor | `app/models/export.py` (`orders_to_csv`) | Regel 2: formatregler i modellaget, ikke i controller |
| Tegnsett | UTF-8 med BOM (`utf-8-sig`) | Uten BOM tolker Excel filen som Windows-1252 og æøå blir feil |
| Skilletegn | Semikolon | Norsk Excel bruker komma som desimaltegn og forventer `;` |
| Datoformat | ISO `ÅÅÅÅ-MM-DD` | Gjenkjennes som dato av Excel og Numbers |
| Total | Heltall i kroner, uten tusenskille | Kan summeres direkte i regneark |
| Status | Norske visningsnavn (`OrderStatus.LABELS`, `PaymentStatus.LABELS`) | Leses av regnskap, ikke utviklere |
| Filter | Samme parsing som listevisningen, delt i `_order_filters()` | CSV og tabell viser alltid de samme ordrene |
| Rute | `GET /admin/bestillinger.csv` | Ren nedlasting, ingen tilstandsendring, så ingen CSRF trengs; beskyttet av `admin_required` |

## Berørte filer
- models: `app/models/export.py` (ny)
- controllers: `app/controllers/admin.py` (ny rute `orders_csv`, hjelper `_order_filters`)
- templates: `app/templates/admin/orders.html` (knapp som sender med filteret)
- tests: `tests/test_export.py` (ny)

## Steg
1. `orders_to_csv(orders) -> str` i `models/export.py`
2. Trekk ut filterparsing i `_order_filters()` og bruk den i både `orders` og `orders_csv`
3. Rute som returnerer `text/csv; charset=utf-8` med `Content-Disposition: attachment`
4. Knapp i malen som videresender `request.args`
5. Tester

## Verifisering
- Tester: enhetstest av `orders_to_csv` (BOM, header, æøå, statusnavn); rutetest for
  `text/csv`, vedlegg, riktig antall rader, at filteret virker og at ikke-admin avvises.
- `python -m pytest -q` grønn.
- Manuell sjekk: last ned etter `python seed.py`, åpne i Excel og Numbers.

## Risiko / åpne spørsmål
- Mac-Excel med engelsk region forventer komma. Kan gjøres konfigurerbart senere ved behov.
