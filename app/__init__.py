import os
import secrets

from flask import Flask, abort, request, session

from app.config import Config
from app.models import entities
from app.models.images import ImageGenerator, ImageStore
from app.models.repositories import create_repositories

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv er valgfritt
    pass


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    # Config leses ved import; les miljøvariabler på nytt etter load_dotenv()
    app.config["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY")
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)
    app.extensions["repos"] = create_repositories(app.config)
    app.extensions["image_store"] = ImageStore(
        app.config["PENDING_IMAGE_DIR"], app.static_folder
    )
    app.extensions["image_generator"] = ImageGenerator(
        app.config.get("ANTHROPIC_API_KEY"), app.config["IMAGE_MODEL"]
    )

    from app.controllers import account, admin, shop
    from app.controllers.helpers import get_cart, get_current_user

    app.register_blueprint(shop.bp)
    app.register_blueprint(account.bp)
    app.register_blueprint(admin.bp)

    @app.before_request
    def csrf_protect():
        if request.method == "POST" and not app.config.get("TESTING_DISABLE_CSRF"):
            token = session.get("_csrf")
            if not token or request.form.get("_csrf") != token:
                abort(400, "Ugyldig skjema (CSRF). Last siden på nytt og prøv igjen.")

    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

    # Globaler er synlige også i importerte makroer (i motsetning til context processors)
    app.jinja_env.globals.update(
        csrf_token=csrf_token,
        EVENT_CATEGORIES=entities.EVENT_CATEGORIES,
        ALLERGENS=entities.ALLERGENS,
        DIETS=entities.DIETS,
        ORDER_STATUS=entities.OrderStatus.LABELS,
        PAYMENT_STATUS=entities.PaymentStatus.LABELS,
    )

    @app.context_processor
    def inject_user():
        return {"current_user": get_current_user(), "cart_count": get_cart().count}

    @app.template_filter("nok")
    def nok(value: int) -> str:
        return f"{value:,} kr".replace(",", " ")

    @app.template_filter("dato")
    def dato(value) -> str:
        return value.strftime("%d.%m.%Y") if value else ""

    return app
