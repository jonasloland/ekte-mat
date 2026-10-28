"""Tester for at kunden kan avbestille en innsendt bestilling (plan 0003)."""
from datetime import date, timedelta

import pytest

from app.models.entities import Order, OrderLine, OrderStatus, PaymentStatus
from app.models.services import ValidationError, cancel_order_by_customer, register_customer
from tests.conftest import login


def _order(repos, customer_id, dish, status=OrderStatus.SUBMITTED):
    return repos.orders.add(
        Order(None, customer_id, date.today() + timedelta(days=10), 10, "Gate 1",
              [OrderLine(dish.id, dish.name, 200, 10)], status=status)
    )


# --- Modellaget ---------------------------------------------------------------


def test_customer_can_cancel_own_submitted_order(repos, customer, dish):
    order = _order(repos, customer.id, dish)
    cancel_order_by_customer(repos, order.id, customer.id)
    assert repos.orders.get(order.id).status == OrderStatus.CANCELLED


def test_customer_cannot_cancel_others_order(repos, customer, dish):
    other = register_customer(repos, "annen@test.no", "Annen", "passord123")
    order = _order(repos, other.id, dish)
    with pytest.raises(ValidationError):
        cancel_order_by_customer(repos, order.id, customer.id)
    assert repos.orders.get(order.id).status == OrderStatus.SUBMITTED


def test_customer_cannot_cancel_approved_order(repos, customer, dish):
    order = _order(repos, customer.id, dish, status=OrderStatus.APPROVED)
    with pytest.raises(ValidationError):
        cancel_order_by_customer(repos, order.id, customer.id)
    assert repos.orders.get(order.id).status == OrderStatus.APPROVED


def test_cancel_keeps_payment_status(repos, customer, dish):
    order = _order(repos, customer.id, dish)
    cancel_order_by_customer(repos, order.id, customer.id)
    assert repos.orders.get(order.id).payment_status == PaymentStatus.UNPAID


# --- Gjennom rutene -----------------------------------------------------------


def test_cancel_button_only_shown_for_submitted(client, repos, customer, dish):
    submitted = _order(repos, customer.id, dish)
    approved = _order(repos, customer.id, dish, status=OrderStatus.APPROVED)
    login(client, "kunde@test.no", "passord123")
    assert "Avbestill" in client.get(f"/konto/bestillinger/{submitted.id}").get_data(as_text=True)
    assert "Avbestill" not in client.get(f"/konto/bestillinger/{approved.id}").get_data(as_text=True)


def test_cancel_route_cancels_own_order(client, repos, customer, dish):
    order = _order(repos, customer.id, dish)
    login(client, "kunde@test.no", "passord123")
    resp = client.post(f"/konto/bestillinger/{order.id}/avbestill")
    assert resp.status_code == 302
    assert repos.orders.get(order.id).status == OrderStatus.CANCELLED


def test_cancel_route_404_for_others_order(client, repos, customer, dish):
    other = register_customer(repos, "annen@test.no", "Annen", "passord123")
    order = _order(repos, other.id, dish)
    login(client, "kunde@test.no", "passord123")
    assert client.post(f"/konto/bestillinger/{order.id}/avbestill").status_code == 404
    assert repos.orders.get(order.id).status == OrderStatus.SUBMITTED


def test_cancel_route_refuses_approved_order(client, repos, customer, dish):
    order = _order(repos, customer.id, dish, status=OrderStatus.APPROVED)
    login(client, "kunde@test.no", "passord123")
    client.post(f"/konto/bestillinger/{order.id}/avbestill")
    assert repos.orders.get(order.id).status == OrderStatus.APPROVED