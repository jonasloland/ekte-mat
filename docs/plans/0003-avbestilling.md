# 0003 – Kunden kan avbestille en innsendt bestilling

Issue: #2

## Mål
Kunden skal kunne avbestille sin egen ordre så lenge den har status «innsendt», uten å måtte ringe.

## Endringer
- `app/models/services.py`: ny funksjon `avbestill_ordre(ordre_id, kunde_id)`
  - sjekker at ordren tilhører kunden
  - sjekker at status er «innsendt»
  - setter status til «kansellert»
- `app/controllers/account.py`: ny POST-rute som kaller funksjonen
- `app/templates/account/order_detail.html`: knapp «Avbestill» som bare vises når status er «innsendt», i et skjema med `{{ csrf() }}`

## Tester
- Kunden kan avbestille sin egen innsendte ordre → status blir «kansellert»
- Kunden kan ikke avbestille en annen kundes ordre
- Kunden kan ikke avbestille en godkjent ordre

## Ferdig når
Alle testene over er grønne med `python -m pytest -q`.
