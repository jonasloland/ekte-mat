"""Fabrikk for repositories. STORAGE_BACKEND velger implementasjon: "sqlite" eller "neo4j"."""
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
    if backend == "neo4j":
        # Lat import: SQLite-oppsettet skal virke uten Neo4j-driveren
        from app.models.repositories.neo4j import (
            Neo4jDatabase,
            Neo4jDishRepository,
            Neo4jOrderRepository,
            Neo4jQuestionRepository,
            Neo4jUserRepository,
        )

        db = Neo4jDatabase.from_config(config)
        db.init_schema()
        return Repositories(
            users=Neo4jUserRepository(db),
            dishes=Neo4jDishRepository(db),
            orders=Neo4jOrderRepository(db),
            questions=Neo4jQuestionRepository(db),
        )
    raise ValueError(f"Ukjent STORAGE_BACKEND: {backend}")


def reset_storage(config: dict) -> None:
    """Tømmer lagringen (brukes av seed-scriptet)."""
    backend = config.get("STORAGE_BACKEND", "sqlite")
    if backend == "sqlite":
        SqliteDatabase(config["DATABASE_PATH"]).reset()
    elif backend == "neo4j":
        from app.models.repositories.neo4j import Neo4jDatabase

        Neo4jDatabase.from_config(config).reset()
