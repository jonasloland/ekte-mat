"""Forretningslogikk som bruker flere repositories. Controllere kaller disse
i stedet for å sette sammen domeneobjekter selv."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from app.models.cart import Cart
from app.models.entities import (
    Dish,
    GuestGroup,
    Order,
    OrderLine,
    OrderStatus,
    PaymentStatus,
    User,
)
from app.models.repositories.base import Repositories


class ValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


# --- Konto -------------------------------------------------------------------


def register_customer(repos: Repositories, email: str, name: str, password: str) -> User:
    errors = []
    if "@" not in email:
        errors.append("Ugyldig e-postadresse.")
    if not name.strip():
        errors.append("Navn må fylles ut.")
    if len(password) < 8:
        errors.append("Passordet må ha minst 8 tegn.")
    if not errors and repos.users.get_by_email(email):
        errors.append("Det finnes allerede en konto med denne e-postadressen.")
    if errors:
        raise ValidationError(errors)
    return repos.users.add(
        User(None, email, name.strip(), generate_password_hash(password), "customer")
    )


def create_admin(repos: Repositories, email: str, name: str, password: str) -> User:
    return repos.users.add(User(None, email, name, generate_password_hash(password), "admin"))


def authenticate(repos: Repositories, email: str, password: str) -> Optional[User]:
    user = repos.users.get_by_email(email)
    if user and check_password_hash(user.password_hash, password):
        return user
    return None


# --- Meny --------------------------------------------------------------------


def filter_dishes(
    dishes: Iterable[Dish],
    exclude_allergens: Iterable[str] = (),
    require_diets: Iterable[str] = (),
) -> list[Dish]:
    """Skjuler retter med noen av allergenene og beholder kun retter som
    oppfyller alle diettene. Tomme valg gir ingen filtrering."""
    excluded = set(exclude_allergens)
    required = set(require_diets)
    return [
        d for d in dishes
        if not excluded & set(d.allergens) and required <= set(d.diets)
    ]


# --- Bestilling --------------------------------------------------------------


def place_order(
    repos: Repositories,
    customer_id: int,
    cart: Cart,
    event_date: date,
    guest_count: int,
    delivery_address: str,
    guest_groups: list[GuestGroup],
    daily_capacity: int,
    today: Optional[date] = None,
) -> Order:
    lines = []
    errors = []
    for item in cart.items():
        if item.quantity < item.dish.min_order:
            errors.append(
                f"Minstebestilling for «{item.dish.name}» er {item.dish.min_order}."
            )
        lines.append(
            OrderLine(
                item.dish.id, item.dish.name, item.dish.price_nok, item.quantity,
                list(item.dish.allergens),
            )
        )
    order = Order(
        id=None,
        customer_id=customer_id,
        event_date=event_date,
        guest_count=guest_count,
        delivery_address=delivery_address.strip(),
        lines=lines,
        guest_groups=[g for g in guest_groups if g.name.strip() and g.count > 0],
        status=OrderStatus.SUBMITTED,
        payment_status=PaymentStatus.UNPAID,
    )
    errors += order.validate(today)
    if not errors:
        booked = repos.orders.guests_on_date(event_date)
        if booked + guest_count > daily_capacity:
            free = max(daily_capacity - booked, 0)
            errors.append(
                f"Kjøkkenet har bare kapasitet til {free} flere gjester "
                f"{event_date.strftime('%d.%m.%Y')}. Velg en annen dato."
            )
    if errors:
        raise ValidationError(errors)
    order = repos.orders.add(order)
    cart.clear()
    return order


def change_order_status(
    repos: Repositories, order_id: int, new_status: str, new_payment_status: str
) -> Order:
    order = repos.orders.get(order_id)
    if order is None:
        raise ValidationError(["Bestillingen finnes ikke."])
    errors = []
    if new_status not in OrderStatus.LABELS:
        errors.append("Ukjent ordrestatus.")
    elif new_status != order.status and not OrderStatus.can_transition(order.status, new_status):
        errors.append(
            f"Kan ikke gå fra «{OrderStatus.LABELS[order.status]}» "
            f"til «{OrderStatus.LABELS[new_status]}»."
        )
    if new_payment_status not in PaymentStatus.LABELS:
        errors.append("Ukjent betalingsstatus.")
    if errors:
        raise ValidationError(errors)
    repos.orders.update_status(order_id, new_status, new_payment_status)
    order.status, order.payment_status = new_status, new_payment_status
    return order


def cancel_order_by_customer(repos: Repositories, order_id: int, customer_id: int) -> Order:
    order = repos.orders.get(order_id)
    if order is None or order.customer_id != customer_id:
        raise ValidationError(["Bestillingen finnes ikke."])
    if not order.can_customer_cancel:
        raise ValidationError(["Bare innsendte bestillinger kan avbestilles."])
    repos.orders.update_status(order.id, OrderStatus.CANCELLED, order.payment_status)
    order.status = OrderStatus.CANCELLED
    return order


def copy_order_to_cart(repos: Repositories, order: Order, cart: Cart) -> list[str]:
    """Legger retter fra en tidligere ordre i kurven (bedriftskunder som bestiller
    det samme hver uke). Returnerer navn på retter som ikke lenger kan bestilles."""
    skipped = []
    for line in order.lines:
        dish = repos.dishes.get(line.dish_id)
        if dish is None or not dish.published:
            skipped.append(line.dish_name)
            continue
        cart.set_quantity(dish.id, max(line.quantity, dish.min_order))
    return skipped
