"""Adminpanel: matretter (A1), bilder (A2), bestillinger (A3), spørsmål (A4)
og kjøkkenvisning (ekstra)."""
from datetime import date, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from app.controllers.helpers import admin_required, get_current_user, repos
from app.models.entities import ALLERGENS, DIETS, EVENT_CATEGORIES, Dish, OrderStatus
from app.models.images import ImageError
from app.models.services import ValidationError, change_order_status

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@admin_required
def require_admin():
    """Alle ruter i blueprinten krever admin."""


def _image_store():
    return current_app.extensions["image_store"]


def _get_dish(dish_id) -> Dish:
    dish = repos().dishes.get(dish_id)
    if dish is None:
        abort(404)
    return dish


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@bp.get("/")
def dashboard():
    r = repos()
    return render_template(
        "admin/dashboard.html",
        new_orders=r.orders.list_filtered(status=OrderStatus.SUBMITTED),
        open_questions=r.questions.list_all(unanswered_only=True),
        dish_count=len(r.dishes.list_all()),
    )


# --- A1 Matretter ------------------------------------------------------------


@bp.get("/retter")
def dishes():
    return render_template("admin/dishes.html", dishes=repos().dishes.list_all())


def _dish_from_form(form, dish: Dish | None = None) -> Dish:
    dish = dish or Dish(None, "", "", 0)
    dish.name = form.get("name", "").strip()
    dish.description = form.get("description", "").strip()
    try:
        dish.price_nok = int(form.get("price_nok", ""))
        dish.min_order = int(form.get("min_order", ""))
    except ValueError:
        dish.price_nok, dish.min_order = -1, 0  # fanges av validate()
    dish.event_categories = [c for c in form.getlist("event_categories") if c in EVENT_CATEGORIES]
    dish.allergens = [a for a in form.getlist("allergens") if a in ALLERGENS]
    dish.diets = [d for d in form.getlist("diets") if d in DIETS]
    dish.published = form.get("published") == "on"
    dish.origin = form.get("origin", "").strip() or None
    return dish


@bp.route("/retter/ny", methods=["GET", "POST"])
def dish_new():
    dish = Dish(None, "", "", 0)
    if request.method == "POST":
        dish = _dish_from_form(request.form)
        errors = dish.validate()
        if not errors:
            repos().dishes.add(dish)
            flash(f"«{dish.name}» er opprettet. Legg gjerne til et bilde.", "success")
            return redirect(url_for("admin.dish_image", dish_id=dish.id))
        for e in errors:
            flash(e, "error")
    return render_template("admin/dish_form.html", dish=dish)


@bp.route("/retter/<int:dish_id>", methods=["GET", "POST"])
def dish_edit(dish_id):
    dish = _get_dish(dish_id)
    if request.method == "POST":
        dish = _dish_from_form(request.form, dish)
        errors = dish.validate()
        if not errors:
            repos().dishes.update(dish)
            flash("Endringene er lagret.", "success")
            return redirect(url_for("admin.dishes"))
        for e in errors:
            flash(e, "error")
    return render_template("admin/dish_form.html", dish=dish)


@bp.post("/retter/<int:dish_id>/slett")
def dish_delete(dish_id):
    dish = _get_dish(dish_id)
    repos().dishes.delete(dish.id)
    _image_store().delete(dish.image_path)
    flash(f"«{dish.name}» er slettet.", "success")
    return redirect(url_for("admin.dishes"))


# --- A2 Bilder ---------------------------------------------------------------


@bp.get("/retter/<int:dish_id>/bilde")
def dish_image(dish_id):
    return render_template("admin/dish_image.html", dish=_get_dish(dish_id), preview=None)


@bp.post("/retter/<int:dish_id>/bilde/forhandsvis")
def dish_image_preview(dish_id):
    """Lager et ventende bilde (opplastet eller generert) og viser det for godkjenning."""
    dish = _get_dish(dish_id)
    store = _image_store()
    prompt = None
    source = "opplastet"
    try:
        if request.form.get("mode") == "generate":
            prompt = request.form.get("prompt", "").strip()
            data, ext, source = current_app.extensions["image_generator"].generate(prompt)
        else:
            upload = request.files.get("image")
            if not upload or not upload.filename:
                raise ImageError("Velg en bildefil.")
            ext = store.extension_for(upload.filename)
            data = upload.read()
        token = store.save_pending(data, ext)
    except ImageError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.dish_image", dish_id=dish.id))
    preview = {"token": token, "prompt": prompt, "source": source}
    return render_template("admin/dish_image.html", dish=dish, preview=preview)


@bp.get("/bilder/ventende/<token>")
def pending_image(token):
    try:
        return send_file(_image_store().pending_path(token))
    except ImageError:
        abort(404)


@bp.post("/retter/<int:dish_id>/bilde/lagre")
def dish_image_save(dish_id):
    dish = _get_dish(dish_id)
    store = _image_store()
    try:
        new_path = store.commit(request.form.get("token", ""))
    except ImageError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.dish_image", dish_id=dish.id))
    old_path = dish.image_path
    dish.image_path = new_path
    dish.image_prompt = request.form.get("prompt") or None
    repos().dishes.update(dish)
    store.delete(old_path)
    flash("Bildet er lagret.", "success")
    return redirect(url_for("admin.dishes"))


# --- A3 Bestillinger ---------------------------------------------------------


@bp.get("/bestillinger")
def orders():
    status = request.args.get("status") or None
    if status not in OrderStatus.LABELS:
        status = None
    date_from = _parse_date(request.args.get("fra"))
    date_to = _parse_date(request.args.get("til"))
    return render_template(
        "admin/orders.html",
        orders=repos().orders.list_filtered(status, date_from, date_to),
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@bp.get("/bestillinger/<int:order_id>")
def order_detail(order_id):
    order = repos().orders.get(order_id)
    if order is None:
        abort(404)
    return render_template(
        "admin/order_detail.html",
        order=order,
        questions=repos().questions.list_for_order(order.id),
        allowed_statuses=[order.status, *sorted(OrderStatus.TRANSITIONS[order.status])],
        booked=repos().orders.guests_on_date(order.event_date),
        capacity=current_app.config["DAILY_GUEST_CAPACITY"],
    )


@bp.post("/bestillinger/<int:order_id>/status")
def order_status(order_id):
    try:
        change_order_status(
            repos(), order_id, request.form.get("status", ""), request.form.get("payment_status", "")
        )
        flash("Status er oppdatert.", "success")
    except ValidationError as e:
        for err in e.errors:
            flash(err, "error")
    return redirect(url_for("admin.order_detail", order_id=order_id))


# --- A4 Spørsmål -------------------------------------------------------------


@bp.get("/sporsmal")
def questions():
    show_all = request.args.get("alle") == "1"
    return render_template(
        "admin/questions.html",
        questions=repos().questions.list_all(unanswered_only=not show_all),
        show_all=show_all,
    )


@bp.post("/sporsmal/<int:question_id>/svar")
def answer_question(question_id):
    question = repos().questions.get(question_id)
    if question is None:
        abort(404)
    answer = request.form.get("answer", "").strip()
    if not answer:
        flash("Svaret kan ikke være tomt.", "error")
    else:
        repos().questions.answer(question.id, answer, get_current_user().id)
        flash("Svaret er sendt til kunden.", "success")
    return redirect(request.referrer or url_for("admin.questions"))


# --- Ekstra: kjøkkenvisning --------------------------------------------------


@bp.get("/kjokken")
def kitchen():
    """Kommende godkjente ordrer med allergier uthevet – for kokkene."""
    today = date.today()
    active = [
        o for o in repos().orders.list_filtered(date_from=today, date_to=today + timedelta(days=14))
        if o.status in (OrderStatus.APPROVED, OrderStatus.IN_PREPARATION)
    ]
    return render_template("admin/kitchen.html", orders=active)
