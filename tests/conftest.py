import os

import pytest

from app import create_app
from app.models.entities import Dish
from app.models.repositories import reset_storage
from app.models.services import create_admin, register_customer

# TEST_STORAGE_BACKEND=neo4j kjører hele testsuiten mot Neo4j (tømmer databasen før hver test)
BACKEND = os.environ.get("TEST_STORAGE_BACKEND", "sqlite")


@pytest.fixture
def app(tmp_path):
    static = tmp_path / "static"
    app = create_app(
        {
            "TESTING": True,
            "TESTING_DISABLE_CSRF": True,
            "STORAGE_BACKEND": BACKEND,
            "DATABASE_PATH": str(tmp_path / "test.sqlite3"),
            "PENDING_IMAGE_DIR": str(tmp_path / "pending"),
            "ANTHROPIC_API_KEY": None,
            "DAILY_GUEST_CAPACITY": 100,
        }
    )
    if BACKEND == "neo4j":
        reset_storage(app.config)
    # Bildelageret skal ikke skrive i det ekte static-katalogen under test
    from app.models.images import ImageGenerator, ImageStore

    app.extensions["image_store"] = ImageStore(str(tmp_path / "pending"), str(static))
    app.extensions["image_generator"] = ImageGenerator(None)
    app.static_folder = str(static)
    return app


@pytest.fixture
def repos(app):
    return app.extensions["repos"]


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def customer(repos):
    return register_customer(repos, "kunde@test.no", "Test Kunde", "passord123")


@pytest.fixture
def admin(repos):
    return create_admin(repos, "admin@test.no", "Test Admin", "admin12345")


@pytest.fixture
def dish(repos):
    return repos.dishes.add(
        Dish(None, "Fårikål", "Lam og kål", 200, min_order=10,
             event_categories=["konfirmasjon"], allergens=["selleri"], published=True)
    )


def login(client, email, password):
    return client.post("/konto/logg-inn", data={"email": email, "password": password})
