"""Enhetstester for modellaget (uten HTTP)."""
from datetime import date, timedelta

import pytest

from app.models.cart import Cart, CartError
from app.models.entities import Dish, GuestGroup, OrderStatus, PaymentStatus
from app.models.images import sanitize_svg
from app.models.services import (
    ValidationError,
    authenticate,
    change_order_status,
    filter_dishes,
    place_order,
    register_customer,
)

FUTURE = date.today() + timedelta(days=10)


def test_dish_validation_catches_bad_values():
    dish = Dish(None, "", "", -5, min_order=0, allergens=["ukjent"])
    errors = dish.validate()
    assert len(errors) == 4


def test_dish_repository_roundtrip(repos):
    d = repos.dishes.add(Dish(None, "Suppe", "God", 99, 5, ["bursdag"], ["melk"], ["vegetar"], True))
    loaded = repos.dishes.get(d.id)
    assert loaded == d
    loaded.published = False
    repos.dishes.update(loaded)
    assert repos.dishes.list_published() == []
    repos.dishes.delete(d.id)
    assert repos.dishes.get(d.id) is None


def test_list_published_filters_on_event(repos, dish):
    assert [d.id for d in repos.dishes.list_published("konfirmasjon")] == [dish.id]
    assert repos.dishes.list_published("julebord") == []


def test_cart_rejects_quantity_under_min_order(repos, dish):
    cart = Cart({}, repos.dishes)
    with pytest.raises(CartError):
        cart.add(dish.id, dish.min_order - 1)
    cart.add(dish.id, dish.min_order)
    assert cart.total_nok == dish.min_order * dish.price_nok


def test_cart_zero_removes_and_unpublished_is_rejected(repos, dish):
    cart = Cart({}, repos.dishes)
    cart.add(dish.id, 10)
    cart.set_quantity(dish.id, 0)
    assert cart.is_empty()
    dish.published = False
    repos.dishes.update(dish)
    with pytest.raises(CartError):
        cart.add(dish.id, 10)


def test_register_and_authenticate(repos):
    register_customer(repos, "A@Test.no", "A", "hemmelig123")
    assert authenticate(repos, "a@test.no", "hemmelig123") is not None
    assert authenticate(repos, "a@test.no", "feil") is None
    with pytest.raises(ValidationError):
        register_customer(repos, "a@test.no", "Dupl", "hemmelig123")


def _place(repos, customer, dish, **kw):
    cart = Cart({}, repos.dishes)
    cart.add(dish.id, 10)
    args = dict(event_date=FUTURE, guest_count=10, delivery_address="Gate 1",
                guest_groups=[GuestGroup("Barn", 3, "nøtter")], daily_capacity=100)
    args.update(kw)
    return place_order(repos, customer.id, cart, **args), cart


def test_place_order_snapshots_lines_and_clears_cart(repos, customer, dish):
    order, cart = _place(repos, customer, dish)
    assert cart.is_empty()
    loaded = repos.orders.get(order.id)
    assert loaded.total_nok == 2000
    assert loaded.lines[0].allergens == ["selleri"]
    assert loaded.guest_groups[0].notes == "nøtter"
    assert loaded.status == OrderStatus.SUBMITTED
    # Endring av retten etterpå skal ikke endre ordren
    dish.price_nok = 999
    repos.dishes.update(dish)
    assert repos.orders.get(order.id).total_nok == 2000


def test_place_order_validates(repos, customer, dish):
    with pytest.raises(ValidationError) as exc:
        _place(repos, customer, dish, event_date=date.today(), delivery_address=" ")
    assert len(exc.value.errors) == 2


def test_capacity_check(repos, customer, dish):
    _place(repos, customer, dish, guest_count=90)
    with pytest.raises(ValidationError, match="kapasitet"):
        _place(repos, customer, dish, guest_count=20)


def test_status_transitions(repos, customer, dish):
    order, _ = _place(repos, customer, dish)
    with pytest.raises(ValidationError):
        change_order_status(repos, order.id, OrderStatus.DELIVERED, PaymentStatus.UNPAID)
    change_order_status(repos, order.id, OrderStatus.APPROVED, PaymentStatus.DEPOSIT)
    change_order_status(repos, order.id, OrderStatus.IN_PREPARATION, PaymentStatus.INVOICED)
    change_order_status(repos, order.id, OrderStatus.DELIVERED, PaymentStatus.PAID)
    loaded = repos.orders.get(order.id)
    assert (loaded.status, loaded.payment_status) == ("levert", "betalt")


def test_admin_order_filter(repos, customer, dish):
    order, _ = _place(repos, customer, dish)
    assert [o.id for o in repos.orders.list_filtered(status="innsendt")] == [order.id]
    assert repos.orders.list_filtered(status="levert") == []
    assert repos.orders.list_filtered(date_from=FUTURE + timedelta(days=1)) == []


def test_sanitize_svg_strips_scripts():
    dirty = '<svg onload="alert(1)"><script>alert(2)</script><a href="javascript:x">y</a></svg>'
    clean = sanitize_svg(dirty)
    assert "script" not in clean and "onload" not in clean and "javascript" not in clean


def test_filter_dishes_on_allergens_and_diets():
    brod = Dish(1, "Brød", "", 50, allergens=["gluten"], diets=["vegan"])
    ost = Dish(2, "Ost", "", 50, allergens=["melk"], diets=["vegetar", "glutenfri"])
    salat = Dish(3, "Salat", "", 50, diets=["vegan", "glutenfri"])
    dishes = [brod, ost, salat]

    assert filter_dishes(dishes) == dishes
    assert filter_dishes(dishes, exclude_allergens=["gluten"]) == [ost, salat]
    assert filter_dishes(dishes, exclude_allergens=["gluten", "melk"]) == [salat]
    assert filter_dishes(dishes, require_diets=["vegan"]) == [brod, salat]
    assert filter_dishes(dishes, require_diets=["vegan", "glutenfri"]) == [salat]
    assert filter_dishes(dishes, ["melk"], ["glutenfri"]) == [salat]
