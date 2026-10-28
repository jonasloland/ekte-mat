"""Domeneklasser for Ekte Mat. Ren Python – ingen kunnskap om lagring."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

# --- Faste verdilister -------------------------------------------------------

EVENT_CATEGORIES = {
    "bursdag": "Bursdag",
    "konfirmasjon": "Konfirmasjon",
    "bryllup": "Bryllup",
    "konferanse": "Konferanse",
    "julebord": "Julebord",
    "minnestund": "Minnestund",
    "sommerfest": "Sommerfest",
}

ALLERGENS = {
    "gluten": "Gluten",
    "melk": "Melk/laktose",
    "egg": "Egg",
    "notter": "Nøtter",
    "peanotter": "Peanøtter",
    "fisk": "Fisk",
    "skalldyr": "Skalldyr",
    "soya": "Soya",
    "selleri": "Selleri",
    "sennep": "Sennep",
    "sesam": "Sesam",
}

DIETS = {
    "vegetar": "Vegetar",
    "vegan": "Vegan",
    "glutenfri": "Glutenfri",
    "laktosefri": "Laktosefri",
    "halal": "Halal",
}


class OrderStatus:
    SUBMITTED = "innsendt"
    APPROVED = "godkjent"
    IN_PREPARATION = "under_tilberedning"
    DELIVERED = "levert"
    REJECTED = "avvist"
    CANCELLED = "kansellert"

    LABELS = {
        SUBMITTED: "Innsendt",
        APPROVED: "Godkjent",
        IN_PREPARATION: "Under tilberedning",
        DELIVERED: "Levert",
        REJECTED: "Avvist",
        CANCELLED: "Kansellert",
    }

    # Lovlige overganger: innsendt → godkjent → under tilberedning → levert,
    # med avvist/kansellert som sidespor før levering.
    TRANSITIONS = {
        SUBMITTED: {APPROVED, REJECTED, CANCELLED},
        APPROVED: {IN_PREPARATION, CANCELLED},
        IN_PREPARATION: {DELIVERED, CANCELLED},
        DELIVERED: set(),
        REJECTED: set(),
        CANCELLED: set(),
    }

    @classmethod
    def can_transition(cls, current: str, new: str) -> bool:
        return new in cls.TRANSITIONS.get(current, set())


class PaymentStatus:
    UNPAID = "ikke_betalt"
    DEPOSIT = "depositum"
    INVOICED = "fakturert"
    PAID = "betalt"

    LABELS = {
        UNPAID: "Ikke betalt",
        DEPOSIT: "Depositum",
        INVOICED: "Fakturert",
        PAID: "Betalt",
    }


# --- Entiteter ---------------------------------------------------------------


@dataclass
class User:
    id: Optional[int]
    email: str
    name: str
    password_hash: str
    role: str = "customer"  # "customer" | "admin"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass
class Dish:
    id: Optional[int]
    name: str
    description: str
    price_nok: int  # pris per porsjon i hele kroner
    min_order: int = 1
    event_categories: list[str] = field(default_factory=list)
    allergens: list[str] = field(default_factory=list)
    diets: list[str] = field(default_factory=list)
    published: bool = False
    image_path: Optional[str] = None  # relativ til static/
    image_prompt: Optional[str] = None
    origin: Optional[str] = None  # matens opprinnelse (ekstra)

    def validate(self) -> list[str]:
        errors = []
        if not self.name.strip():
            errors.append("Navn må fylles ut.")
        if self.price_nok < 0:
            errors.append("Pris kan ikke være negativ.")
        if self.min_order < 1:
            errors.append("Minstebestilling må være minst 1.")
        for c in self.event_categories:
            if c not in EVENT_CATEGORIES:
                errors.append(f"Ukjent eventkategori: {c}")
        for a in self.allergens:
            if a not in ALLERGENS:
                errors.append(f"Ukjent allergen: {a}")
        for d in self.diets:
            if d not in DIETS:
                errors.append(f"Ukjent diett: {d}")
        return errors


@dataclass
class OrderLine:
    dish_id: int
    dish_name: str  # øyeblikksbilde, så gamle ordrer ikke endres når retten endres
    unit_price_nok: int
    quantity: int
    allergens: list[str] = field(default_factory=list)

    @property
    def subtotal_nok(self) -> int:
        return self.unit_price_nok * self.quantity


@dataclass
class GuestGroup:
    name: str
    count: int
    notes: str = ""


@dataclass
class Order:
    id: Optional[int]
    customer_id: int
    event_date: date
    guest_count: int
    delivery_address: str
    lines: list[OrderLine] = field(default_factory=list)
    guest_groups: list[GuestGroup] = field(default_factory=list)
    status: str = OrderStatus.SUBMITTED
    payment_status: str = PaymentStatus.UNPAID
    created_at: datetime = field(default_factory=datetime.now)
    customer_name: Optional[str] = None  # fylles inn av repository ved oppslag

    @property
    def total_nok(self) -> int:
        return sum(line.subtotal_nok for line in self.lines)

    @property
    def all_allergens(self) -> set[str]:
        return {a for line in self.lines for a in line.allergens}
    
    @property
    def can_customer_cancel(self) -> bool:
        """Kunden kan selv avbestille så lenge ordren ikke er behandlet."""
        return self.status == OrderStatus.SUBMITTED

    def validate(self, today: Optional[date] = None) -> list[str]:
        today = today or date.today()
        errors = []
        if not self.lines:
            errors.append("Bestillingen må inneholde minst én rett.")
        if self.event_date <= today:
            errors.append("Eventdato må være i fremtiden.")
        if self.guest_count < 1:
            errors.append("Antall gjester må være minst 1.")
        if not self.delivery_address.strip():
            errors.append("Leveringsadresse må fylles ut.")
        if sum(g.count for g in self.guest_groups) > self.guest_count:
            errors.append("Gjestegruppene har flere gjester enn totalt antall gjester.")
        return errors


@dataclass
class Question:
    id: Optional[int]
    order_id: int
    customer_id: int
    body: str
    created_at: datetime = field(default_factory=datetime.now)
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None
    answered_by: Optional[int] = None

    @property
    def is_answered(self) -> bool:
        return self.answer is not None
