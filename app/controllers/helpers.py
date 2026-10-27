"""Felles hjelpere for controllere: tilgang til repositories, innlogget bruker,
handlekurv i sesjonen og tilgangskontroll."""
from functools import wraps

from flask import abort, current_app, flash, g, redirect, request, session, url_for

from app.models.cart import Cart
from app.models.repositories.base import Repositories


def repos() -> Repositories:
    return current_app.extensions["repos"]


def get_current_user():
    if "current_user" not in g:
        user_id = session.get("user_id")
        g.current_user = repos().users.get(user_id) if user_id else None
    return g.current_user


def get_cart() -> Cart:
    return Cart(session.get("cart", {}), repos().dishes)


def save_cart(cart: Cart) -> None:
    session["cart"] = cart.to_dict()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            flash("Logg inn for å fortsette.", "info")
            return redirect(url_for("account.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("account.login", next=request.full_path))
        if not user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def safe_next(target: str | None) -> str | None:
    """Tillat kun interne redirect-mål (unngår open redirect)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None
