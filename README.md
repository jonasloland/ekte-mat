# Ekte Mat – bestillingssystem for catering

Flask-app (MVC) med kundeside og adminpanel. Lagring i SQLite bak repository-grensesnitt,
slik at den kan byttes til Neo4j uten å endre controllere eller views.

## Installere
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # fyll inn SECRET_KEY, evt. ANTHROPIC_API_KEY
```

## Seede testdata
```bash
python seed.py
```
Sletter eksisterende data og lager 10 retter (9 publisert), 4 bestillinger og 2 spørsmål.

| Rolle | E-post | Passord |
|---|---|---|
| Admin | admin@ektemat.no | admin1234 |
| Kunde | kari@example.no | kunde1234 |
| Bedriftskunde | ola@example.no | kunde1234 |

## Kjøre
```bash
python run.py
```
Åpne http://localhost:5050 (kundeside) eller logg inn som admin for `/admin`.

## Teste
```bash
python -m pytest -q
```

## Funksjoner

| Krav | Hvor |
|---|---|
| A1 Matretter (CRUD, publisering) | `/admin/retter` – `controllers/admin.py` |
| A2 Bilder (opplasting eller instruks, forhåndsvisning før lagring) | `/admin/retter/<id>/bilde` – `models/images.py` |
| A3 Bestillinger (filter på status/dato, ordre- og betalingsstatus) | `/admin/bestillinger` |
| A4 Spørsmål | `/admin/sporsmal` |
| C1 Meny etter event | `/` |
| C2 Handlekurv med minstebestilling | `/handlekurv` – `models/cart.py` |
| C3 Innlogging og bestilling med gjestegrupper | `/konto/logg-inn`, `/bestill` |
| C4 Mine bestillinger | `/konto/bestillinger` |
| C5 Spørsmål om bestilling | `/konto/bestillinger/<id>` |

### Ekstra (og hvem det er for)
- **Kjøkkenvisning med allergier uthevet** (`/admin/kjokken`) – kokkene, som må se allergener tydelig for å unngå feil.
- **Kapasitetssjekk** (`DAILY_GUEST_CAPACITY`) – driftsleder, så kjøkkenet ikke overbookes en dag.
- **«Bestill det samme igjen»** – bedriftskunder som bestiller samme lunsj hver uke.
- **Matens opprinnelse på kortene** – kunder som bryr seg om kortreist mat.

### Bildegenerering
Med `ANTHROPIC_API_KEY` i `.env` lager admin en SVG-illustrasjon fra en tekstinstruks via Claude
(`IMAGE_MODEL`, standard `claude-opus-5-5`). Uten nøkkel lages en enkel plassholder, så appen
virker uten nøkkel. SVG fra tjenesten og opplastede SVG-er renses for script før lagring.

## Arkitektur
Se [CLAUDE.md](CLAUDE.md) for mappestruktur og regler, og [docs/plans/](docs/plans/) for planer.

**Bytte til Neo4j (oblig 5):** lag `app/models/repositories/neo4j.py` som implementerer klassene i
`base.py`, og legg til en gren for `STORAGE_BACKEND=neo4j` i `create_repositories()`.
