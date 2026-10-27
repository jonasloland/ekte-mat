# Ekte Mat – prosjektbriefing for Claude Code

## Hva systemet er
Bestillingssystem for cateringfirmaet Ekte Mat. Én Flask-app med to deler:
- **Kundeside** (`shop`, `account`): meny gruppert etter eventtype, handlekurv med minstebestilling,
  innsending av bestilling med gjestegrupper/allergier, «mine bestillinger» og spørsmål.
- **Adminpanel** (`admin`): CRUD for matretter, bilder (opplasting eller generert fra instruks, med
  forhåndsvisning), bestillinger med status/betalingsstatus, svar på spørsmål, kjøkkenvisning.

## MVC-oppsett
```
app/
  models/          # M – domene + ALL datatilgang
    entities.py      domeneklasser, statuser og overganger (ingen lagring)
    repositories/    base.py = abstrakte grensesnitt, sqlite.py = eneste sted med SQL,
                     __init__.py = fabrikk (bytt til Neo4j her i oblig 5)
    cart.py          handlekurvregler
    services.py      forretningslogikk på tvers av repositories (bestilling, status, auth)
    images.py        bildelagring + bildegenerering (Claude/plassholder)
  controllers/     # C – Flask-blueprints: shop.py, account.py, admin.py, helpers.py
  templates/       # V – Jinja2-maler (shop/, account/, admin/, _macros.html)
  static/
```

## Kjøre og teste
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed.py
python run.py          # http://localhost:5050
python -m pytest -q
```

## Teamets regler
1. **Lagdeling:** Controllere og maler skal aldri importere `sqlite3` eller `app.models.repositories.sqlite`.
   De bruker `repos()` fra `controllers/helpers.py`, som gir de abstrakte grensesnittene.
2. **Forretningsregler i modellaget** (`entities.py`, `cart.py`, `services.py`) – ikke i controllere eller maler.
3. **Ny lagringsmetode = metode i `base.py` + implementasjon i `sqlite.py` + test.**
4. **Planlegg før større features** i plan mode, og commit planen til `docs/plans/NNNN-navn.md`
   før koden.
5. **Tester:** Ny funksjonalitet skal ha test i `tests/`. `python -m pytest -q` skal være grønn før commit.
6. **Hemmeligheter:** API-nøkler kun i `.env` (ignorert av git). Aldri hardkod eller commit nøkler.
7. **Sikkerhet:** Alle POST-skjemaer må ha `{{ csrf() }}`. Kunder får kun se egne ordrer (404 ellers).
8. **Språk:** UI og domenebegreper på norsk; kode-identifikatorer på engelsk.
