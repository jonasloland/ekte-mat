"""Kontrakttester for repositoriene (plan 0006). Samme tester kjøres mot hver backend, slik at
SQLite og Neo4j garantert oppfører seg likt for controllerne.

SQLite kjøres alltid. Neo4j kjøres med TEST_STORAGE_BACKEND=neo4j (krever at Neo4j kjører, se README).
"""
import os
from datetime import date, datetime, timedelta

import pytest

from app.config import Config
from app.models.entities import (
    Dish,
    GuestGroup,
    Order,
    OrderLine,
    OrderStatus,
    PaymentStatus,
    Question,
    User,
)
from app.models.repositories import create_repositories, reset_storage

NEO4J = os.environ.get("TEST_STORAGE_BACKEND") == "neo4j"
DAY = date.today() + timedelta(days=20)


@pytest.fixture(params=[
    "sqlite",
    pytest.param("neo4j", marks=pytest.mark.skipif(
        not NEO4J, reason="sett TEST_STORAGE_BACKEND=neo4j for å teste mot Neo4j")),
])
def repos(request, tmp_path):
    config = {
        "STORAGE_BACKEND": request.param,
        "DATABASE_PATH": str(tmp_path / "contract.sqlite3"),
        "NEO4J_URI": Config.NEO4J_URI,
        "NEO4J_USER": Config.NEO4J_USER,
        "NEO4J_PASSWORD": Config.NEO4J_PASSWORD,
        "NEO4J_DATABASE": Config.NEO4J_DATABASE,
    }
    reset_storage(config)
    return create_repositories(config)


@pytest.fixture
def kari(repos):
    return repos.users.add(User(None, "Kari@Example.no", "Kari Nordmann", "hash"))


def _dish(repos, name, **kw):
    kw.setdefault("published", True)
    return repos.dishes.add(Dish(None, name, f"Om {name}", 100, **kw))


def _order(repos, customer, dishes, day=DAY, guests=10, **kw):
    lines = [OrderLine(d.id, d.name, d.price_nok, 10, list(d.allergens)) for d in dishes]
    return repos.orders.add(Order(None, customer.id, day, guests, "Bryggen 1", lines, **kw))


# --- Brukere -------------------------------------------------------------------


def test_users_add_get_and_email_lookup(repos, kari):
    assert isinstance(kari.id, int)
    assert repos.users.get(kari.id).name == "Kari Nordmann"
    assert repos.users.get_by_email(" KARI@example.no ").id == kari.id
    assert repos.users.get(9999) is None and repos.users.get_by_email("x@y.no") is None


def test_users_get_unique_increasing_ids(repos, kari):
    ola = repos.users.add(User(None, "ola@example.no", "Ola", "hash", role="admin"))
    assert ola.id != kari.id and repos.users.get(ola.id).is_admin


# --- Matretter -----------------------------------------------------------------


def test_dish_roundtrip_keeps_lists_in_order(repos):
    dish = _dish(repos, "Laksesnitter", min_order=30, allergens=["fisk", "gluten", "egg"],
                 diets=["laktosefri"], event_categories=["konferanse", "bursdag"],
                 origin="Hardanger", image_path="uploads/dishes/x.svg")
    got = repos.dishes.get(dish.id)
    assert got == dish


def test_dish_lists_sorted_by_name_and_published_filter(repos):
    _dish(repos, "Pinnekjøtt", event_categories=["julebord"])
    _dish(repos, "Bløtkake", event_categories=["bursdag"])
    _dish(repos, "Fårikål", event_categories=["julebord"], published=False)
    assert [d.name for d in repos.dishes.list_all()] == ["Bløtkake", "Fårikål", "Pinnekjøtt"]
    assert [d.name for d in repos.dishes.list_published()] == ["Bløtkake", "Pinnekjøtt"]
    assert [d.name for d in repos.dishes.list_published("julebord")] == ["Pinnekjøtt"]


def test_dish_update_replaces_fields_and_lists(repos):
    dish = _dish(repos, "Wraps", allergens=["gluten", "melk"], diets=["vegetar"])
    dish.name, dish.price_nok, dish.published = "Vegetar-wraps", 89, False
    dish.allergens, dish.diets, dish.origin = ["sesam"], [], None
    repos.dishes.update(dish)
    assert repos.dishes.get(dish.id) == dish


def test_dish_delete_keeps_old_order_lines(repos, kari):
    dish = _dish(repos, "Ribbe", allergens=["sennep"])
    order = _order(repos, kari, [dish])
    repos.dishes.delete(dish.id)
    assert repos.dishes.get(dish.id) is None
    line = repos.orders.get(order.id).lines[0]
    assert (line.dish_name, line.unit_price_nok, line.allergens) == ("Ribbe", 100, ["sennep"])


# --- Bestillinger --------------------------------------------------------------


def test_order_roundtrip_with_lines_and_groups(repos, kari):
    a, b = _dish(repos, "A", allergens=["egg"]), _dish(repos, "B")
    order = _order(repos, kari, [a, b], guest_groups=[GuestGroup("Barn", 4, "nøtter"),
                                                     GuestGroup("Voksne", 6)])
    got = repos.orders.get(order.id)
    assert got.customer_name == "Kari Nordmann" and got.customer_id == kari.id
    assert got.event_date == DAY and isinstance(got.created_at, datetime)
    assert [l.dish_name for l in got.lines] == ["A", "B"] and got.lines[0].allergens == ["egg"]
    assert [(g.name, g.count, g.notes) for g in got.guest_groups] == [
        ("Barn", 4, "nøtter"), ("Voksne", 6, "")]
    assert got.total_nok == 2000 and repos.orders.get(9999) is None


def test_order_lists_and_filters(repos, kari):
    ola = repos.users.add(User(None, "ola@example.no", "Ola", "hash"))
    dish = _dish(repos, "Suppe")
    early = _order(repos, kari, [dish], day=DAY)
    late = _order(repos, kari, [dish], day=DAY + timedelta(days=5), status=OrderStatus.APPROVED)
    other = _order(repos, ola, [dish], day=DAY + timedelta(days=2))
    assert [o.id for o in repos.orders.list_for_customer(kari.id)] == [late.id, early.id]
    assert [o.id for o in repos.orders.list_filtered()] == [early.id, other.id, late.id]
    assert [o.id for o in repos.orders.list_filtered(status=OrderStatus.APPROVED)] == [late.id]
    assert [o.id for o in repos.orders.list_filtered(
        date_from=DAY + timedelta(days=1), date_to=DAY + timedelta(days=3))] == [other.id]


def test_order_status_update_and_guest_capacity(repos, kari):
    dish = _dish(repos, "Suppe")
    a = _order(repos, kari, [dish], guests=30)
    b = _order(repos, kari, [dish], guests=20)
    _order(repos, kari, [dish], day=DAY + timedelta(days=1), guests=99)
    assert repos.orders.guests_on_date(DAY) == 50
    repos.orders.update_status(b.id, OrderStatus.CANCELLED, PaymentStatus.DEPOSIT)
    got = repos.orders.get(b.id)
    assert (got.status, got.payment_status) == (OrderStatus.CANCELLED, PaymentStatus.DEPOSIT)
    assert repos.orders.guests_on_date(DAY) == 30
    assert repos.orders.guests_on_date(DAY + timedelta(days=30)) == 0
    assert repos.orders.get(a.id).status == OrderStatus.SUBMITTED


# --- Spørsmål ------------------------------------------------------------------


def test_questions_add_list_and_answer(repos, kari):
    admin = repos.users.add(User(None, "admin@ektemat.no", "Ada", "hash", role="admin"))
    order = _order(repos, kari, [_dish(repos, "Suppe")])
    first = repos.questions.add(Question(None, order.id, kari.id, "Kl. 11?",
                                         created_at=datetime(2026, 1, 1, 10, 0)))
    second = repos.questions.add(Question(None, order.id, kari.id, "Servise?",
                                          created_at=datetime(2026, 1, 1, 12, 0)))
    assert [q.id for q in repos.questions.list_for_order(order.id)] == [first.id, second.id]
    assert [q.id for q in repos.questions.list_all()] == [second.id, first.id]

    repos.questions.answer(first.id, "Ja", admin.id)
    got = repos.questions.get(first.id)
    assert got.is_answered and got.answer == "Ja" and got.answered_by == admin.id
    assert got.order_id == order.id and got.customer_id == kari.id
    assert [q.id for q in repos.questions.list_all(unanswered_only=True)] == [second.id]
    assert repos.questions.get(9999) is None
