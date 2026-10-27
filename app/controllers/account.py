"""Kundekonto: innlogging/registrering (C3), mine bestillinger (C4) og spørsmål (C5)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from app.controllers.helpers import (
    get_cart,
    get_current_user,
    login_required,
    repos,
    safe_next,
    save_cart,
)
from app.models.cart import CartError
from app.models.entities import Question
from app.models.services import (
    ValidationError,
    authenticate,
    copy_order_to_cart,
    register_customer,
)

bp = Blueprint("account", __name__, url_prefix="/konto")


def _login(user):
    cart = session.get("cart")
    session.clear()  # ny sesjon ved innlogging; behold handlekurven
    session["user_id"] = user.id
    if cart:
        session["cart"] = cart


@bp.route("/logg-inn", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = authenticate(repos(), request.form.get("email", ""), request.form.get("password", ""))
        if user:
            _login(user)
            default = url_for("admin.dashboard") if user.is_admin else url_for("shop.menu")
            return redirect(safe_next(request.args.get("next")) or default)
        flash("Feil e-post eller passord.", "error")
    return render_template("account/login.html")


@bp.route("/registrer", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            user = register_customer(
                repos(),
                request.form.get("email", ""),
                request.form.get("name", ""),
                request.form.get("password", ""),
            )
            _login(user)
            flash("Velkommen til Ekte Mat!", "success")
            return redirect(safe_next(request.args.get("next")) or url_for("shop.menu"))
        except ValidationError as e:
            for err in e.errors:
                flash(err, "error")
    return render_template("account/register.html", form=request.form)


@bp.post("/logg-ut")
def logout():
    session.clear()
    return redirect(url_for("shop.menu"))


def _own_order(order_id):
    order = repos().orders.get(order_id)
    if order is None or order.customer_id != get_current_user().id:
        abort(404)
    return order


@bp.get("/bestillinger")
@login_required
def orders():
    return render_template(
        "account/orders.html", orders=repos().orders.list_for_customer(get_current_user().id)
    )


@bp.get("/bestillinger/<int:order_id>")
@login_required
def order_detail(order_id):
    order = _own_order(order_id)
    return render_template(
        "account/order_detail.html",
        order=order,
        questions=repos().questions.list_for_order(order.id),
    )


@bp.post("/bestillinger/<int:order_id>/sporsmal")
@login_required
def ask_question(order_id):
    order = _own_order(order_id)
    body = request.form.get("body", "").strip()
    if not body:
        flash("Skriv et spørsmål.", "error")
    else:
        repos().questions.add(Question(None, order.id, get_current_user().id, body))
        flash("Spørsmålet er sendt. Vi svarer så snart vi kan.", "success")
    return redirect(url_for("account.order_detail", order_id=order.id))


@bp.post("/bestillinger/<int:order_id>/bestill-igjen")
@login_required
def reorder(order_id):
    order = _own_order(order_id)
    cart = get_cart()
    try:
        skipped = copy_order_to_cart(repos(), order, cart)
    except CartError as e:
        flash(str(e), "error")
        return redirect(url_for("account.order_detail", order_id=order.id))
    save_cart(cart)
    if skipped:
        flash("Ikke lenger på menyen: " + ", ".join(skipped), "info")
    flash("Rettene fra bestillingen er lagt i handlekurven.", "success")
    return redirect(url_for("shop.cart"))
