# Plan 0003 – Kunden kan avbestille en innsendt bestilling

**Status:** Godkjent
**Ansvarlig:** helenatonnesen
**Interessent/behov:** Kunde – planene endrer seg, og de vil slippe å ringe. (Issue #2)

## Mål
Kunden kan selv avbestille sin egen bestilling så lenge den har status «innsendt».
Andres bestillinger og bestillinger som er godkjent (eller lenger ut i løpet) kan ikke avbestilles.

## Berørte filer
- models: `entities.py` (ny egenskap `Order.can_customer_cancel`),
  `services.py` (ny funksjon `cancel_order_by_customer`)
- controllers: `account.py` (ny POST-rute `/konto/bestillinger/<id>/avbestill`)
- templates: `account/order_detail.html` (knapp «Avbestill» med `{{ csrf() }}`)
- tests: ny fil `tests/test_cancel_order.py`

## Steg
1. Legg til `can_customer_cancel` på `Order` – regelen bor i modellaget.
2. Lag `cancel_order_by_customer(repos, order_id, customer_id)` som sjekker eierskap og status,
   og setter status til «kansellert» med eksisterende `update_status` (ingen ny repository-metode).
3. Lag ruten `cancel_order` som bruker `_own_order` (404 for andres ordrer) og kaller tjenesten.
4. Vis knappen «Avbestill» bare når `order.can_customer_cancel` er sann.
5. Skriv tester og kjør `python -m pytest -q`.

## Verifisering
- Tester: egen innsendt ordre blir kansellert; andres ordre gir feil/404 og forblir uendret;
  godkjent ordre kan ikke avbestilles; knappen vises bare for innsendte ordrer.
- Manuell sjekk: logg inn som kunde, åpne en innsendt bestilling, trykk «Avbestill» og se at
  status blir «Kansellert» og knappen forsvinner.

## Risiko / åpne spørsmål
- Betalingsstatus endres ikke ved avbestilling. Bør depositum håndteres? Avklares med teamet.

