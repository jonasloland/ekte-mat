# Plan 0001 – MVP-arkitektur og alle kjernefeatures

**Status:** Gjennomført
**Gjelder:** A1–A4, C1–C5, seed, tester

## Mål
Én Flask-app med kundeside og adminpanel der lagringen kan byttes til Neo4j (oblig 5)
uten å endre controllere eller views.

## Beslutninger
| Tema | Valg | Begrunnelse |
|---|---|---|
| Lagring | SQLite via `sqlite3` (ingen ORM) | Ingen ekstra avhengigheter; SQL holdes på ett sted |
| Datatilgang | Abstrakte repositories i `base.py`, SQLite-implementasjon i `sqlite.py`, fabrikk i `__init__.py` | Controllere kjenner bare grensesnittet → Neo4j-bytte er lokalt i modellaget |
| Lister (allergener, kategorier) | JSON-kolonner | Enkelt i SQLite; blir relasjoner i Neo4j |
| Ordrelinjer | Kopi av navn/pris/allergener ved bestilling | Gamle ordrer skal ikke endre seg når en rett endres |
| Handlekurv | `{dish_id: antall}` i Flask-sesjonen, regler i `models/cart.py` | Fungerer uten innlogging |
| Statusoverganger | Tabell `OrderStatus.TRANSITIONS` i domenet | Én kilde til sannhet; testbart |
| Auth | Werkzeug-passordhash + `session["user_id"]`, rolle `admin`/`customer` | «Enkel kundeinnlogging holder» |
| CSRF | Token i sesjon, sjekkes i `before_request` | Uten Flask-WTF-avhengighet |
| Bilder | Ventende fil i `instance/` → forhåndsvisning → flytt til `static/uploads` ved lagring | Kravet om forhåndsvisning før lagring |
| Bildegenerering | Claude lager SVG fra instruks; plassholder uten nøkkel | Virker for alle i gruppa uten API-nøkkel |

## Steg
1. Domeneklasser og statuser (`entities.py`)
2. Repository-grensesnitt + SQLite-implementasjon
3. Handlekurv og tjenester (bestilling, statusendring, auth)
4. Blueprints `shop`, `account`, `admin`
5. Maler og CSS
6. Seed-script
7. Tester: modell (enhet) og ruter (integrasjon), inkl. tilgangskontroll og CSRF

## Verifisering
- `python -m pytest -q` grønn
- Manuell gjennomgang: kunde legger i kurv → avvises under minstebestilling → bestiller →
  admin godkjenner → kunde ser status; spørsmål/svar begge veier; bilde forhåndsvises før lagring.

## Risiko / åpne spørsmål
- Kapasitet er én global grense per dag (`DAILY_GUEST_CAPACITY`) – kan utvides per rett.
- Ingen e-postvarsling ved statusendring.
