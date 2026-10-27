"""SQLite-implementasjon av repositoriene. Eneste sted i appen som kjører SQL."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator, Optional

from app.models.entities import (
    Dish,
    GuestGroup,
    Order,
    OrderLine,
    OrderStatus,
    Question,
    User,
)
from app.models.repositories.base import (
    DishRepository,
    OrderRepository,
    QuestionRepository,
    UserRepository,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer'
);
CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_nok INTEGER NOT NULL,
    min_order INTEGER NOT NULL DEFAULT 1,
    event_categories TEXT NOT NULL DEFAULT '[]',
    allergens TEXT NOT NULL DEFAULT '[]',
    diets TEXT NOT NULL DEFAULT '[]',
    published INTEGER NOT NULL DEFAULT 0,
    image_path TEXT,
    image_prompt TEXT,
    origin TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES users(id),
    event_date TEXT NOT NULL,
    guest_count INTEGER NOT NULL,
    delivery_address TEXT NOT NULL,
    status TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    dish_id INTEGER NOT NULL,
    dish_name TEXT NOT NULL,
    unit_price_nok INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    allergens TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS guest_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    count INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    answer TEXT,
    answered_at TEXT,
    answered_by INTEGER REFERENCES users(id)
);
"""


class SqliteDatabase:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def reset(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                "DROP TABLE IF EXISTS questions; DROP TABLE IF EXISTS guest_groups;"
                "DROP TABLE IF EXISTS order_lines; DROP TABLE IF EXISTS orders;"
                "DROP TABLE IF EXISTS dishes; DROP TABLE IF EXISTS users;"
            )
            conn.executescript(SCHEMA)


def _dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class SqliteUserRepository(UserRepository):
    def __init__(self, db: SqliteDatabase):
        self.db = db

    @staticmethod
    def _row(row) -> User:
        return User(row["id"], row["email"], row["name"], row["password_hash"], row["role"])

    def get(self, user_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row(row) if row else None

    def get_by_email(self, email):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
        return self._row(row) if row else None

    def add(self, user):
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
                (user.email.strip().lower(), user.name, user.password_hash, user.role),
            )
            user.id = cur.lastrowid
        return user


class SqliteDishRepository(DishRepository):
    def __init__(self, db: SqliteDatabase):
        self.db = db

    @staticmethod
    def _row(row) -> Dish:
        return Dish(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            price_nok=row["price_nok"],
            min_order=row["min_order"],
            event_categories=json.loads(row["event_categories"]),
            allergens=json.loads(row["allergens"]),
            diets=json.loads(row["diets"]),
            published=bool(row["published"]),
            image_path=row["image_path"],
            image_prompt=row["image_prompt"],
            origin=row["origin"],
        )

    @staticmethod
    def _params(d: Dish) -> tuple:
        return (
            d.name, d.description, d.price_nok, d.min_order,
            json.dumps(d.event_categories), json.dumps(d.allergens), json.dumps(d.diets),
            int(d.published), d.image_path, d.image_prompt, d.origin,
        )

    def get(self, dish_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
        return self._row(row) if row else None

    def list_all(self):
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM dishes ORDER BY name").fetchall()
        return [self._row(r) for r in rows]

    def list_published(self, event_category=None):
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM dishes WHERE published = 1 ORDER BY name"
            ).fetchall()
        dishes = [self._row(r) for r in rows]
        if event_category:
            dishes = [d for d in dishes if event_category in d.event_categories]
        return dishes

    def add(self, dish):
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO dishes (name, description, price_nok, min_order, event_categories,"
                " allergens, diets, published, image_path, image_prompt, origin)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._params(dish),
            )
            dish.id = cur.lastrowid
        return dish

    def update(self, dish):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE dishes SET name = ?, description = ?, price_nok = ?, min_order = ?,"
                " event_categories = ?, allergens = ?, diets = ?, published = ?,"
                " image_path = ?, image_prompt = ?, origin = ? WHERE id = ?",
                self._params(dish) + (dish.id,),
            )

    def delete(self, dish_id):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))


class SqliteOrderRepository(OrderRepository):
    def __init__(self, db: SqliteDatabase):
        self.db = db

    def _load(self, conn, row) -> Order:
        lines = [
            OrderLine(
                r["dish_id"], r["dish_name"], r["unit_price_nok"], r["quantity"],
                json.loads(r["allergens"]),
            )
            for r in conn.execute(
                "SELECT * FROM order_lines WHERE order_id = ? ORDER BY id", (row["id"],)
            )
        ]
        groups = [
            GuestGroup(r["name"], r["count"], r["notes"])
            for r in conn.execute(
                "SELECT * FROM guest_groups WHERE order_id = ? ORDER BY id", (row["id"],)
            )
        ]
        return Order(
            id=row["id"],
            customer_id=row["customer_id"],
            event_date=date.fromisoformat(row["event_date"]),
            guest_count=row["guest_count"],
            delivery_address=row["delivery_address"],
            lines=lines,
            guest_groups=groups,
            status=row["status"],
            payment_status=row["payment_status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            customer_name=row["customer_name"],
        )

    _SELECT = (
        "SELECT o.*, u.name AS customer_name FROM orders o"
        " JOIN users u ON u.id = o.customer_id"
    )

    def get(self, order_id):
        with self.db.connect() as conn:
            row = conn.execute(self._SELECT + " WHERE o.id = ?", (order_id,)).fetchone()
            return self._load(conn, row) if row else None

    def list_for_customer(self, customer_id):
        with self.db.connect() as conn:
            rows = conn.execute(
                self._SELECT + " WHERE o.customer_id = ? ORDER BY o.event_date DESC",
                (customer_id,),
            ).fetchall()
            return [self._load(conn, r) for r in rows]

    def list_filtered(self, status=None, date_from=None, date_to=None):
        clauses, params = [], []
        if status:
            clauses.append("o.status = ?")
            params.append(status)
        if date_from:
            clauses.append("o.event_date >= ?")
            params.append(date_from.isoformat())
        if date_to:
            clauses.append("o.event_date <= ?")
            params.append(date_to.isoformat())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.db.connect() as conn:
            rows = conn.execute(
                self._SELECT + where + " ORDER BY o.event_date", params
            ).fetchall()
            return [self._load(conn, r) for r in rows]

    def add(self, order):
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO orders (customer_id, event_date, guest_count, delivery_address,"
                " status, payment_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    order.customer_id, order.event_date.isoformat(), order.guest_count,
                    order.delivery_address, order.status, order.payment_status,
                    order.created_at.isoformat(timespec="seconds"),
                ),
            )
            order.id = cur.lastrowid
            conn.executemany(
                "INSERT INTO order_lines (order_id, dish_id, dish_name, unit_price_nok,"
                " quantity, allergens) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (order.id, l.dish_id, l.dish_name, l.unit_price_nok, l.quantity,
                     json.dumps(l.allergens))
                    for l in order.lines
                ],
            )
            conn.executemany(
                "INSERT INTO guest_groups (order_id, name, count, notes) VALUES (?, ?, ?, ?)",
                [(order.id, g.name, g.count, g.notes) for g in order.guest_groups],
            )
        return order

    def update_status(self, order_id, status, payment_status):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE orders SET status = ?, payment_status = ? WHERE id = ?",
                (status, payment_status, order_id),
            )

    def guests_on_date(self, event_date):
        inactive = (OrderStatus.REJECTED, OrderStatus.CANCELLED)
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(guest_count), 0) AS n FROM orders"
                " WHERE event_date = ? AND status NOT IN (?, ?)",
                (event_date.isoformat(), *inactive),
            ).fetchone()
        return row["n"]


class SqliteQuestionRepository(QuestionRepository):
    def __init__(self, db: SqliteDatabase):
        self.db = db

    @staticmethod
    def _row(row) -> Question:
        return Question(
            id=row["id"],
            order_id=row["order_id"],
            customer_id=row["customer_id"],
            body=row["body"],
            created_at=datetime.fromisoformat(row["created_at"]),
            answer=row["answer"],
            answered_at=_dt(row["answered_at"]),
            answered_by=row["answered_by"],
        )

    def get(self, question_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        return self._row(row) if row else None

    def list_for_order(self, order_id):
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM questions WHERE order_id = ? ORDER BY created_at", (order_id,)
            ).fetchall()
        return [self._row(r) for r in rows]

    def list_all(self, unanswered_only=False):
        sql = "SELECT * FROM questions"
        if unanswered_only:
            sql += " WHERE answer IS NULL"
        with self.db.connect() as conn:
            rows = conn.execute(sql + " ORDER BY created_at DESC").fetchall()
        return [self._row(r) for r in rows]

    def add(self, question):
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO questions (order_id, customer_id, body, created_at)"
                " VALUES (?, ?, ?, ?)",
                (question.order_id, question.customer_id, question.body,
                 question.created_at.isoformat(timespec="seconds")),
            )
            question.id = cur.lastrowid
        return question

    def answer(self, question_id, answer, admin_id):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE questions SET answer = ?, answered_at = ?, answered_by = ? WHERE id = ?",
                (answer, datetime.now().isoformat(timespec="seconds"), admin_id, question_id),
            )
