# Ekte Mat – bestillingssystem for catering

Flask-app (MVC) med kundeside og adminpanel. Lagringen ligger bak repository-grensesnitt og kan
kjøre på **SQLite** (standard) eller **Neo4j** – controllere og views er de samme.

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

Er port 5050 opptatt (`Address already in use`), velg en annen port:
```bash
PORT=5055 python run.py            # Windows (PowerShell): $env:PORT=5055; python run.py
```
og åpne http://localhost:5055. Unngå port 5060 og 6000 – Chrome blokkerer dem (`ERR_UNSAFE_PORT`).

## Teste
```bash
python -m pytest -q
```

## Kjøre med Neo4j
Krever [Docker Desktop](https://www.docker.com/products/docker-desktop/) (må være startet).

1. Start Neo4j (første gang lastes bildet ned):
   ```bash
   docker run -d --name ektemat-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/ektemat-passord neo4j:5.26
   ```
   Senere holder det med `docker start ektemat-neo4j`.
2. Sett `STORAGE_BACKEND=neo4j` i `.env` (passord og adresse står allerede i `.env.example`).
3. Seed og kjør som vanlig:
   ```bash
   python seed.py
   python run.py
   ```
4. Se grafen i Neo4j Browser på http://localhost:7474 (bruker `neo4j`, passord `ektemat-passord`),
   f.eks. med `MATCH (n) RETURN n LIMIT 100`.

Teste mot Neo4j (kjører hele testsuiten og kontrakttestene mot Neo4j – **tømmer databasen**, så kjør
`python seed.py` etterpå):
```bash
TEST_STORAGE_BACKEND=neo4j python -m pytest -q
```

### Grafmodell
```
(User)-[:PLACED]->(Order)-[:HAS_LINE]->(OrderLine)-[:OF_DISH]->(Dish)
(Order)-[:HAS_GROUP]->(GuestGroup)
(Dish)-[:CONTAINS]->(Allergen)  (Dish)-[:SUITS]->(Diet)  (Dish)-[:SERVED_AT]->(EventCategory)
(User)-[:ASKED]->(Question)-[:ABOUT]->(Order)  (User)-[:ANSWERED]->(Question)
```
Ordrelinjene har en kopi av navn, pris og allergener, så gamle ordrer ikke endres når en rett endres
eller slettes. Heltalls-id-er lages med en `(:Counter)`-node per type. Se
[docs/plans/0006-neo4j.md](docs/plans/0006-neo4j.md).

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
- **Allergen- og diettfilter i menyen** (`/?uten=gluten&kun=vegan`) – kunder med allergier, som raskt
  vil skjule retter de ikke tåler. Logikken ligger i `services.filter_dishes` (plan 0002).
- **Kunden kan avbestille en innsendt bestilling** (knapp på `/konto/bestillinger/<id>`) – kunder
  som får endrede planer og vil slippe å ringe. Bare egne ordrer med status «innsendt» (plan 0003).
- **CSV-eksport av bestillinger** (`/admin/bestillinger.csv`, følger valgt filter) – daglig leder og
  regnskap, som fakturerer i Excel. Semikolon og BOM for norsk Excel, og kundenavn escapes mot
  formelinjeksjon (plan 0004).
- **Favicon, bunntekst med kontaktinfo og utskriftsvennlig kjøkkenvisning** («Skriv ut» på
  `/admin/kjokken`) – kunder som vil kontakte Ekte Mat, og kokker som henger ordrene opp på
  kjøkkenet (plan 0005).

Se [docs/interessenter.md](docs/interessenter.md) for en full oversikt over interessentene og funksjonene deres.

### Bildegenerering
Med `ANTHROPIC_API_KEY` i `.env` lager admin en SVG-illustrasjon fra en tekstinstruks via Claude
(`IMAGE_MODEL`, standard `claude-opus-5-5`). Uten nøkkel lages en enkel plassholder, så appen
virker uten nøkkel. SVG fra tjenesten og opplastede SVG-er renses for script før lagring.

## Arkitektur
Se [CLAUDE.md](CLAUDE.md) for mappestruktur og regler, og [docs/plans/](docs/plans/) for planer.

**Lagring:** `app/models/repositories/base.py` definerer grensesnittene. `sqlite.py` (SQL) og
`neo4j.py` (Cypher) implementerer dem, og `create_repositories()` velger etter `STORAGE_BACKEND`.
`tests/test_repositories.py` kjører de samme kontrakttestene mot begge.
