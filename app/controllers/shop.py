"""Kundesiden: meny (C1), handlekurv (C2) og innsending av bestilling (C3)."""
from datetime import date, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.controllers.helpers import (
    get_cart,
    get_current_user,
    login_required,
    repos,
    save_cart,
)
from app.models.cart import CartError
from app.models.entities import EVENT_CATEGORIES, GuestGroup
from app.models.services import ValidationError, place_order

bp = Blueprint("shop", __name__)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@bp.get("/")
def menu():
    selected = request.args.get("event")
    if selected not in EVENT_CATEGORIES:
        selected = None
    dishes = repos().dishes.list_published()
    groups = []
    for key, label in EVENT_CATEGORIES.items():
        if selected and key != selected:
            continue
        in_group = [d for d in dishes if key in d.event_categories]
        if in_group:
            groups.append((key, label, in_group))
    return render_template("shop/menu.html", groups=groups, selected=selected)


@bp.get("/handlekurv")
def cart():
    return render_template("shop/cart.html", cart=get_cart())


@bp.post("/handlekurv/legg-til/<int:dish_id>")
def cart_add(dish_id):
    cart = get_cart()
    dish = repos().dishes.get(dish_id)
    try:
        cart.add(dish_id, _int(request.form.get("quantity")))
        save_cart(cart)
        flash(f"«{dish.name}» er lagt i handlekurven.", "success")
    except CartError as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("shop.menu"))


@bp.post("/handlekurv/oppdater/<int:dish_id>")
def cart_update(dish_id):
    cart = get_cart()
    try:
        cart.set_quantity(dish_id, _int(request.form.get("quantity")))
        save_cart(cart)
    except CartError as e:
        flash(str(e), "error")
    return redirect(url_for("shop.cart"))


@bp.post("/handlekurv/fjern/<int:dish_id>")
def cart_remove(dish_id):
    cart = get_cart()
    cart.remove(dish_id)
    save_cart(cart)
    return redirect(url_for("shop.cart"))


@bp.route("/bestill", methods=["GET", "POST"])
@login_required
def checkout():
    cart = get_cart()
    if cart.is_empty():
        flash("Handlekurven er tom.", "info")
        return redirect(url_for("shop.menu"))

    form = request.form
    if request.method == "POST":
        groups = [
            GuestGroup(name.strip(), _int(count), notes.strip())
            for name, count, notes in zip(
                form.getlist("group_name"),
                form.getlist("group_count"),
                form.getlist("group_notes"),
            )
        ]
        try:
            event_date = date.fromisoformat(form.get("event_date", ""))
        except ValueError:
            flash("Velg en gyldig eventdato.", "error")
        else:
            try:
                order = place_order(
                    repos(),
                    customer_id=get_current_user().id,
                    cart=cart,
                    event_date=event_date,
                    guest_count=_int(form.get("guest_count")),
                    delivery_address=form.get("delivery_address", ""),
                    guest_groups=groups,
                    daily_capacity=current_app.config["DAILY_GUEST_CAPACITY"],
                )
                save_cart(cart)
                flash("Takk! Bestillingen er sendt inn.", "success")
                return redirect(url_for("account.order_detail", order_id=order.id))
            except ValidationError as e:
                for err in e.errors:
                    flash(err, "error")

    return render_template(
        "shop/checkout.html",
        cart=cart,
        form=form,
        min_date=(date.today() + timedelta(days=1)).isoformat(),
    )
