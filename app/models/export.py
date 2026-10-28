"""Eksport av bestillinger til CSV for regnskap (issue #3, plan 0004)."""
from __future__ import annotations

import csv
import io
from typing import Iterable

from app.models.entities import Order, OrderStatus, PaymentStatus

CSV_HEADER = ["id", "kunde", "eventdato", "gjester", "total", "status", "betalingsstatus"]
CSV_DELIMITER = ";"  # norsk Excel bruker komma som desimaltegn og forventer semikolon
BOM = "﻿"  # gjør at Excel leser filen som UTF-8, så æøå vises riktig
# Celler som starter med disse tegnene tolkes som formler av Excel/Numbers
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: str) -> str:
    """Hindrer CSV-/formelinjeksjon: kundestyrt tekst som ser ut som en formel
    får en apostrof foran, så regnearket viser den som vanlig tekst."""
    return "'" + value if value.startswith(FORMULA_PREFIXES) else value


def orders_to_csv(orders: Iterable[Order]) -> str:
    """Returnerer bestillingene som CSV-tekst med BOM, klar til å lastes ned."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=CSV_DELIMITER, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for o in orders:
        writer.writerow([
            o.id,
            safe_cell(o.customer_name or ""),
            o.event_date.isoformat(),
            o.guest_count,
            o.total_nok,
            OrderStatus.LABELS.get(o.status, o.status),
            PaymentStatus.LABELS.get(o.payment_status, o.payment_status),
        ])
    return BOM + buffer.getvalue()
