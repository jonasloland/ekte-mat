# Interessenter i Ekte Mat

Oversikt over hvem systemet er laget for, hva de trenger, og hvilke funksjoner/ruter i appen som
dekker behovet. Rutene er hentet fra `app/controllers/` (`shop.py`, `account.py`, `admin.py`).

> **Roller i appen:** Det finnes bare to roller, `customer` og `admin`. Kokk og daglig leder har ingen
> egne roller i dag – de logger inn med admin-rollen og bruker delene av adminpanelet som er beskrevet under.

## Kunde (privatperson og bedrift)
**Behov:** Finne mat som passer arrangementet, bestille riktig mengde, oppgi allergier for gjestene,
følge med på bestillingen og stille spørsmål. Bedriftskunder bestiller ofte det samme gang på gang.

| Funksjon | Rute | Kode |
|---|---|---|
| Meny gruppert etter eventtype, med allergener, dietter og matens opprinnelse | `GET /` | `shop.menu` |
| Handlekurv med minstebestilling per rett | `GET /handlekurv`, `POST /handlekurv/legg-til/<id>`, `/oppdater/<id>`, `/fjern/<id>` | `shop.cart*`, `models/cart.py` |
| Bestilling med eventdato, gjesteantall, adresse og gjestegrupper med allergier/notater (kapasitetssjekk per dag) | `GET/POST /bestill` | `shop.checkout`, `services.place_order` |
| Registrering, innlogging og utlogging | `/konto/registrer`, `/konto/logg-inn`, `POST /konto/logg-ut` | `account.*` |
| Mine bestillinger med status (kun egne – 404 ellers) | `GET /konto/bestillinger`, `GET /konto/bestillinger/<id>` | `account.orders`, `account.order_detail` |
| Spørsmål om en bestilling | `POST /konto/bestillinger/<id>/sporsmal` | `account.ask_question` |
| «Bestill det samme igjen» (særlig for bedriftskunder) | `POST /konto/bestillinger/<id>/bestill-igjen` | `account.reorder` |

## Kokk
**Behov:** Vite hva som skal lages de nærmeste dagene, og se allergier så tydelig at det ikke blir feil –
også på papir på kjøkkenbenken.

| Funksjon | Rute | Kode |
|---|---|---|
| Kjøkkenvisning: godkjente ordrer og ordrer under tilberedning de neste 14 dagene, allergener og gjestegruppenotater uthevet | `GET /admin/kjokken` | `admin.kitchen` |
| Utskrift av kjøkkenvisningen (bare ordrene; allergier med fet skrift, ramme og ⚠) | «Skriv ut»-knappen på `/admin/kjokken` | `admin/kitchen.html`, `@media print` i `style.css` |

## Daglig leder
**Behov:** Oversikt over nye bestillinger og åpne spørsmål, godkjenne/avvise ordrer, følge betaling og
unngå at kjøkkenet blir overbooket.

| Funksjon | Rute | Kode |
|---|---|---|
| Oversikt: nye bestillinger, ubesvarte spørsmål, antall retter | `GET /admin/` | `admin.dashboard` |
| Bestillingsliste med filter på status og dato | `GET /admin/bestillinger?status=&fra=&til=` | `admin.orders` |
| Ordredetaljer | `GET /admin/bestillinger/<id>` | `admin.order_detail` |
| Endre ordrestatus og betalingsstatus | `POST /admin/bestillinger/<id>/status` | `admin.order_status` |
| Kapasitetsgrense for gjester per dag | konfig `DAILY_GUEST_CAPACITY` | `config.py`, `services.place_order` |

## Admin
**Behov:** Holde menyen oppdatert med retter, priser og bilder, og svare kundene.

| Funksjon | Rute | Kode |
|---|---|---|
| Liste over retter | `GET /admin/retter` | `admin.dishes` |
| Ny rett / rediger rett (inkl. publisering) | `GET/POST /admin/retter/ny`, `GET/POST /admin/retter/<id>` | `admin.dish_new`, `admin.dish_edit` |
| Slett rett | `POST /admin/retter/<id>/slett` | `admin.dish_delete` |
| Bilde: last opp eller generer fra instruks, forhåndsvis før lagring | `GET /admin/retter/<id>/bilde`, `POST …/bilde/forhandsvis`, `GET /admin/bilder/ventende/<token>`, `POST …/bilde/lagre` | `admin.dish_image*`, `admin.pending_image`, `models/images.py` |
| Spørsmål fra kunder og svar | `GET /admin/sporsmal`, `POST /admin/sporsmal/<id>/svar` | `admin.questions`, `admin.answer_question` |
