"""Fabrikk for repositories. Bytt implementasjon her (f.eks. Neo4j i oblig 5)."""
from app.models.repositories.base import Repositories
from app.models.repositories.sqlite import (
    SqliteDatabase,
    SqliteDishRepository,
    SqliteOrderRepository,
    SqliteQuestionRepository,
    SqliteUserRepository,
)


def create_repositories(config: dict) -> Repositories:
    backend = config.get("STORAGE_BACKEND", "sqlite")
    if backend == "sqlite":
        db = SqliteDatabase(config["DATABASE_PATH"])
        db.init_schema()
        return Repositories(
            users=SqliteUserRepository(db),
            dishes=SqliteDishRepository(db),
            orders=SqliteOrderRepository(db),
            questions=SqliteQuestionRepository(db),
        )
    raise ValueError(f"Ukjent STORAGE_BACKEND: {backend}")


def reset_storage(config: dict) -> None:
    """Tømmer lagringen (brukes av seed-scriptet)."""
    if config.get("STORAGE_BACKEND", "sqlite") == "sqlite":
        SqliteDatabase(config["DATABASE_PATH"]).reset()
