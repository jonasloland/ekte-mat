"""Tester for CSV-eksport av bestillinger (issue #3, plan 0004)."""
import csv
import io
from datetime import date, timedelta

import pytest

from app.models.entities import Order, OrderLine, OrderStatus, PaymentStatus
from app.models.export import BOM, CSV_DELIMITER, CSV_HEADER, orders_to_csv, safe_cell
from tests.conftest import login

DAY = date.today() + timedelta(days=5)


def _rows(text):
    assert text.startswith(BOM)
    return list(csv.reader(io.StringIO(text[len(BOM):]), delimiter=CSV_DELIMITER))


@pytest.fixture
def orders(repos, customer, dish):
    a = repos.orders.add(Order(None, customer.id, DAY, 10, "Bryggen 1",
                               [OrderLine(dish.id, dish.name, 200, 10)]))
    b = repos.orders.add(Order(None, customer.id, DAY + timedelta(days=10), 20, "Bryggen 2",
                               [OrderLine(dish.id, dish.name, 200, 20)],
                               status=OrderStatus.APPROVED,
                               payment_status=PaymentStatus.PAID))
    return a, b


def test_orders_to_csv_header_values_and_norwegian_chars():
    order = Order(None, 1, date(2026, 12, 24), 12, "X",
                  [OrderLine(1, "Fårikål", 250, 12)], customer_name="Bjørn Ærø Ås")
    order.id = 7
    rows = _rows(orders_to_csv([order]))
    assert rows[0] == CSV_HEADER
    assert rows[1] == ["7", "Bjørn Ærø Ås", "2026-12-24", "12", "3000",
                       OrderStatus.LABELS[order.status], PaymentStatus.LABELS[order.payment_status]]


@pytest.mark.parametrize("name", ["=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)", "\t=1"])
def test_orders_to_csv_escapes_formulas_in_customer_name(name):
    order = Order(None, 1, date(2026, 12, 24), 12, "X",
                  [OrderLine(1, "Fårikål", 250, 12)], customer_name=name)
    order.id = 1
    assert _rows(orders_to_csv([order]))[1][1] == "'" + name


def test_safe_cell_leaves_normal_text_alone():
    assert safe_cell("Kari Nordmann") == "Kari Nordmann"
    assert safe_cell("Ola-Bedrift AS") == "Ola-Bedrift AS"
    assert safe_cell("") == ""


def test_orders_to_csv_empty_has_only_header():
    assert _rows(orders_to_csv([])) == [CSV_HEADER]


def test_csv_route_returns_all_orders(client, admin, orders):
    login(client, "admin@test.no", "admin12345")
    resp = client.get("/admin/bestillinger.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "charset=utf-8" in resp.headers["Content-Type"]
    assert "attachment" in resp.headers["Content-Disposition"]
    rows = _rows(resp.get_data().decode("utf-8"))
    assert len(rows) == 1 + len(orders)
    assert {r[1] for r in rows[1:]} == {"Test Kunde"}


def test_csv_route_respects_filters(client, admin, orders):
    login(client, "admin@test.no", "admin12345")
    a, b = orders
    rows = _rows(client.get(f"/admin/bestillinger.csv?til={DAY.isoformat()}").get_data().decode("utf-8"))
    assert [r[0] for r in rows[1:]] == [str(a.id)]
    rows = _rows(client.get(f"/admin/bestillinger.csv?status={b.status}").get_data().decode("utf-8"))
    assert [r[0] for r in rows[1:]] == [str(b.id)]


def test_csv_button_keeps_filter(client, admin, orders):
    login(client, "admin@test.no", "admin12345")
    html = client.get(f"/admin/bestillinger?fra={DAY.isoformat()}").get_data(as_text=True)
    assert "Last ned CSV" in html
    assert f"/admin/bestillinger.csv?fra={DAY.isoformat()}" in html


def test_csv_route_requires_admin(client, customer, orders):
    assert client.get("/admin/bestillinger.csv").status_code == 302
    login(client, "kunde@test.no", "passord123")
    assert client.get("/admin/bestillinger.csv").status_code == 403
