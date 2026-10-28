"""Integrasjonstester gjennom Flask-rutene (controller + view + modell)."""
import io
from datetime import date, timedelta

from app.models.entities import Dish
from tests.conftest import login

FUTURE = (date.today() + timedelta(days=10)).isoformat()


def test_menu_shows_published_dishes(client, dish):
    html = client.get("/").get_data(as_text=True)
    assert "Fårikål" in html and "Konfirmasjon" in html and "Selleri" in html


def test_menu_filter_hides_dishes_with_allergen(client, repos, dish):
    repos.dishes.add(
        Dish(None, "Lefse", "Søt", 40, min_order=10, event_categories=["konfirmasjon"],
             allergens=["gluten"], published=True)
    )
    html = client.get("/?uten=gluten").get_data(as_text=True)
    assert "Fårikål" in html and "Lefse" not in html
    assert "Lefse" not in client.get("/?kun=vegan").get_data(as_text=True)
    assert "Lefse" in client.get("/?uten=ukjent").get_data(as_text=True)


def test_cart_rejects_under_min_order(client, dish):
    client.post(f"/handlekurv/legg-til/{dish.id}", data={"quantity": 2})
    html = client.get("/handlekurv").get_data(as_text=True)
    assert "Minstebestilling" in html
    assert "Handlekurven er tom" in html


def test_full_customer_flow(client, repos, customer, dish):
    client.post(f"/handlekurv/legg-til/{dish.id}", data={"quantity": 12})
    # Bestilling krever innlogging
    assert client.get("/bestill").status_code == 302
    login(client, "kunde@test.no", "passord123")
    resp = client.post("/bestill", data={
        "event_date": FUTURE, "guest_count": 12, "delivery_address": "Gate 1",
        "group_name": ["Barn", ""], "group_count": ["4", ""], "group_notes": ["Nøtteallergi", ""],
    })
    assert resp.status_code == 302
    order = repos.orders.list_for_customer(customer.id)[0]
    assert order.total_nok == 2400 and order.guest_groups[0].name == "Barn"

    html = client.get("/konto/bestillinger").get_data(as_text=True)
    assert f"#{order.id}" in html and "Innsendt" in html

    client.post(f"/konto/bestillinger/{order.id}/sporsmal", data={"body": "Levering kl 12?"})
    assert repos.questions.list_for_order(order.id)[0].body == "Levering kl 12?"


def test_customer_cannot_see_others_orders(client, repos, customer, dish):
    from app.models.services import register_customer
    other = register_customer(repos, "annen@test.no", "Annen", "passord123")
    from app.models.entities import Order, OrderLine
    order = repos.orders.add(Order(None, other.id, date.today() + timedelta(days=5), 10, "X",
                                   [OrderLine(dish.id, dish.name, 200, 10)]))
    login(client, "kunde@test.no", "passord123")
    assert client.get(f"/konto/bestillinger/{order.id}").status_code == 404


def test_admin_requires_admin_role(client, customer, admin):
    assert client.get("/admin/").status_code == 302
    login(client, "kunde@test.no", "passord123")
    assert client.get("/admin/").status_code == 403
    client.post("/konto/logg-ut")
    login(client, "admin@test.no", "admin12345")
    assert client.get("/admin/").status_code == 200


def test_admin_dish_crud(client, repos, admin):
    login(client, "admin@test.no", "admin12345")
    client.post("/admin/retter/ny", data={
        "name": "Lapskaus", "description": "Brun", "price_nok": "120", "min_order": "10",
        "event_categories": ["bursdag"], "allergens": ["selleri"], "published": "on",
    })
    dish = repos.dishes.list_all()[0]
    assert (dish.name, dish.price_nok, dish.published) == ("Lapskaus", 120, True)
    client.post(f"/admin/retter/{dish.id}", data={"name": "Lapskaus", "price_nok": "130", "min_order": "10"})
    assert repos.dishes.get(dish.id).price_nok == 130
    assert repos.dishes.get(dish.id).published is False
    client.post(f"/admin/retter/{dish.id}/slett")
    assert repos.dishes.get(dish.id) is None


def test_admin_image_preview_then_save(client, repos, admin, dish):
    login(client, "admin@test.no", "admin12345")
    # Generert (plassholder siden ingen API-nøkkel i test)
    resp = client.post(f"/admin/retter/{dish.id}/bilde/forhandsvis",
                       data={"mode": "generate", "prompt": "Fårikål ovenfra"})
    html = resp.get_data(as_text=True)
    assert "Forhåndsvisning" in html and repos.dishes.get(dish.id).image_path is None
    token = html.split('name="token" value="')[1].split('"')[0]
    assert client.get(f"/admin/bilder/ventende/{token}").status_code == 200
    client.post(f"/admin/retter/{dish.id}/bilde/lagre", data={"token": token, "prompt": "Fårikål ovenfra"})
    saved = repos.dishes.get(dish.id)
    assert saved.image_path.endswith(token) and saved.image_prompt == "Fårikål ovenfra"

    # Opplasting
    resp = client.post(f"/admin/retter/{dish.id}/bilde/forhandsvis", data={
        "mode": "upload", "image": (io.BytesIO(b"\x89PNG fake"), "bilde.png")},
        content_type="multipart/form-data")
    assert "Forhåndsvisning" in resp.get_data(as_text=True)


def test_admin_rejects_path_traversal_token(client, admin, dish):
    login(client, "admin@test.no", "admin12345")
    assert client.get("/admin/bilder/ventende/..%2F..%2Fsecret").status_code == 404


def test_admin_status_and_answer(client, repos, admin, customer, dish):
    from app.models.entities import Order, OrderLine, Question
    order = repos.orders.add(Order(None, customer.id, date.today() + timedelta(days=5), 10, "X",
                                   [OrderLine(dish.id, dish.name, 200, 10)]))
    q = repos.questions.add(Question(None, order.id, customer.id, "Hei?"))
    login(client, "admin@test.no", "admin12345")
    client.post(f"/admin/bestillinger/{order.id}/status", data={"status": "godkjent", "payment_status": "depositum"})
    assert repos.orders.get(order.id).status == "godkjent"
    client.post(f"/admin/sporsmal/{q.id}/svar", data={"answer": "Hallo!"})
    assert repos.questions.get(q.id).answer == "Hallo!"
    assert "Hallo!" in client.get(f"/admin/bestillinger/{order.id}").get_data(as_text=True)
    assert client.get("/admin/kjokken").status_code == 200


def test_csrf_blocks_post_without_token(app, client, dish):
    app.config["TESTING_DISABLE_CSRF"] = False
    assert client.post(f"/handlekurv/legg-til/{dish.id}", data={"quantity": 10}).status_code == 400
