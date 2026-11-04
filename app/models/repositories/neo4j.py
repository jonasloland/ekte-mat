"""Neo4j-implementasjon av repositoriene (oblig 5). Eneste sted i appen som kjører Cypher.

Grafmodell (se docs/plans/0006-neo4j.md):
  (User)-[:PLACED]->(Order)-[:HAS_LINE]->(OrderLine)-[:OF_DISH]->(Dish)
  (Order)-[:HAS_GROUP]->(GuestGroup)
  (Dish)-[:CONTAINS]->(Allergen), (Dish)-[:SUITS]->(Diet), (Dish)-[:SERVED_AT]->(EventCategory)
  (User)-[:ASKED]->(Question)-[:ABOUT]->(Order), (User)-[:ANSWERED]->(Question)
Heltalls-id-er lages med en (:Counter {name}) per label, så rutene virker som med SQLite.
"""
from __future__ import annotations

import atexit
from datetime import datetime
from typing import Any, Optional

from neo4j import Driver, GraphDatabase

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

CONSTRAINTS = [
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (n:User) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT user_email IF NOT EXISTS FOR (n:User) REQUIRE n.email IS UNIQUE",
    "CREATE CONSTRAINT dish_id IF NOT EXISTS FOR (n:Dish) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (n:Order) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (n:Question) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT allergen_key IF NOT EXISTS FOR (n:Allergen) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT diet_key IF NOT EXISTS FOR (n:Diet) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT event_key IF NOT EXISTS FOR (n:EventCategory) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT counter_name IF NOT EXISTS FOR (n:Counter) REQUIRE n.name IS UNIQUE",
]

# Øker telleren for en label og gir neste id som `new_id`
NEXT_ID = (
    "MERGE (counter:Counter {name: $label}) "
    "SET counter.next = coalesce(counter.next, 0) + 1 "
    "WITH counter.next AS new_id "
)

# Én driver per tilkobling – Flask lager en ny app per test, men driveren er dyr å opprette
_drivers: dict[tuple, Driver] = {}


@atexit.register
def _close_drivers() -> None:
    for driver in _drivers.values():
        driver.close()


def _native(value):
    """Neo4j-datoer/tidspunkter -> Python-objekter."""
    return value.to_native() if hasattr(value, "to_native") else value


def _seconds(value: datetime) -> datetime:
    # Samme presisjon som SQLite-versjonen (isoformat(timespec="seconds"))
    return value.replace(microsecond=0)


class Neo4jDatabase:
    def __init__(self, uri: str, user: str, password: str, database: Optional[str] = None):
        key = (uri, user, password)
        if key not in _drivers:
            _drivers[key] = GraphDatabase.driver(uri, auth=(user, password))
        self.driver = _drivers[key]
        self.database = database or None

    @classmethod
    def from_config(cls, config) -> "Neo4jDatabase":
        return cls(
            config["NEO4J_URI"], config["NEO4J_USER"], config["NEO4J_PASSWORD"],
            config.get("NEO4J_DATABASE"),
        )

    def run(self, query: str, **params: Any) -> list:
        """Kjører én spørring i sin egen transaksjon og returnerer postene."""
        records, _, _ = self.driver.execute_query(query, params, database_=self.database)
        return records

    def write(self, work) -> Any:
        """Kjører `work(tx)` i én skrivetransaksjon (alt eller ingenting)."""
        with self.driver.session(database=self.database) as session:
            return session.execute_write(work)

    def init_schema(self) -> None:
        for statement in CONSTRAINTS:
            self.run(statement)

    def reset(self) -> None:
        self.run("MATCH (n) DETACH DELETE n")
        self.init_schema()


def _user(node) -> User:
    return User(node["id"], node["email"], node["name"], node["password_hash"], node["role"])


class Neo4jUserRepository(UserRepository):
    def __init__(self, db: Neo4jDatabase):
        self.db = db

    def get(self, user_id):
        rows = self.db.run("MATCH (u:User {id: $id}) RETURN u", id=user_id)
        return _user(rows[0]["u"]) if rows else None

    def get_by_email(self, email):
        rows = self.db.run(
            "MATCH (u:User {email: $email}) RETURN u", email=email.strip().lower()
        )
        return _user(rows[0]["u"]) if rows else None

    def add(self, user):
        rows = self.db.run(
            NEXT_ID + "CREATE (u:User {id: new_id, email: $email, name: $name,"
            " password_hash: $password_hash, role: $role}) RETURN u.id AS id",
            label="User", email=user.email.strip().lower(), name=user.name,
            password_hash=user.password_hash, role=user.role,
        )
        user.id = rows[0]["id"]
        return user


# Lister hentes i den rekkefølgen de ble lagret (pos på relasjonen)
_DISH_RETURN = """
RETURN d,
  COLLECT { MATCH (d)-[r:CONTAINS]->(x:Allergen) RETURN x.key ORDER BY r.pos } AS allergens,
  COLLECT { MATCH (d)-[r:SUITS]->(x:Diet) RETURN x.key ORDER BY r.pos } AS diets,
  COLLECT { MATCH (d)-[r:SERVED_AT]->(x:EventCategory) RETURN x.key ORDER BY r.pos } AS events
"""

# Erstatter koblingene til allergener, dietter og anledninger for retten `d`
_DISH_LINKS = """
WITH d
OPTIONAL MATCH (d)-[old:CONTAINS|SUITS|SERVED_AT]->()
DELETE old
WITH DISTINCT d
FOREACH (i IN range(0, size($allergens) - 1) |
  MERGE (x:Allergen {key: $allergens[i]}) CREATE (d)-[:CONTAINS {pos: i}]->(x))
FOREACH (i IN range(0, size($diets) - 1) |
  MERGE (x:Diet {key: $diets[i]}) CREATE (d)-[:SUITS {pos: i}]->(x))
FOREACH (i IN range(0, size($events) - 1) |
  MERGE (x:EventCategory {key: $events[i]}) CREATE (d)-[:SERVED_AT {pos: i}]->(x))
"""


class Neo4jDishRepository(DishRepository):
    def __init__(self, db: Neo4jDatabase):
        self.db = db

    @staticmethod
    def _dish(row) -> Dish:
        d = row["d"]
        return Dish(
            id=d["id"],
            name=d["name"],
            description=d["description"],
            price_nok=d["price_nok"],
            min_order=d["min_order"],
            event_categories=list(row["events"]),
            allergens=list(row["allergens"]),
            diets=list(row["diets"]),
            published=d["published"],
            image_path=d.get("image_path"),
            image_prompt=d.get("image_prompt"),
            origin=d.get("origin"),
        )

    @staticmethod
    def _params(dish: Dish) -> dict:
        return {
            "props": {
                "name": dish.name,
                "description": dish.description,
                "price_nok": dish.price_nok,
                "min_order": dish.min_order,
                "published": dish.published,
                "image_path": dish.image_path,
                "image_prompt": dish.image_prompt,
                "origin": dish.origin,
            },
            "allergens": list(dish.allergens),
            "diets": list(dish.diets),
            "events": list(dish.event_categories),
        }

    def get(self, dish_id):
        rows = self.db.run("MATCH (d:Dish {id: $id})" + _DISH_RETURN, id=dish_id)
        return self._dish(rows[0]) if rows else None

    def list_all(self):
        rows = self.db.run("MATCH (d:Dish)" + _DISH_RETURN + "ORDER BY d.name")
        return [self._dish(r) for r in rows]

    def list_published(self, event_category=None):
        if event_category:
            query = "MATCH (d:Dish {published: true})-[:SERVED_AT]->(:EventCategory {key: $event})"
        else:
            query = "MATCH (d:Dish {published: true})"
        rows = self.db.run(query + _DISH_RETURN + "ORDER BY d.name", event=event_category)
        return [self._dish(r) for r in rows]

    def add(self, dish):
        rows = self.db.run(
            NEXT_ID + "CREATE (d:Dish {id: new_id}) SET d += $props"
            + _DISH_LINKS + "RETURN d.id AS id",
            label="Dish", **self._params(dish),
        )
        dish.id = rows[0]["id"]
        return dish

    def update(self, dish):
        self.db.run(
            "MATCH (d:Dish {id: $id}) SET d += $props" + _DISH_LINKS,
            id=dish.id, **self._params(dish),
        )

    def delete(self, dish_id):
        # Ordrelinjene beholder kopien av navn og pris; bare OF_DISH-koblingen forsvinner
        self.db.run("MATCH (d:Dish {id: $id}) DETACH DELETE d", id=dish_id)


_ORDER_RETURN = """
RETURN o, u.id AS customer_id, u.name AS customer_name,
  COLLECT { MATCH (o)-[:HAS_LINE]->(l:OrderLine) RETURN l ORDER BY l.pos } AS lines,
  COLLECT { MATCH (o)-[:HAS_GROUP]->(g:GuestGroup) RETURN g ORDER BY g.pos } AS groups
"""


class Neo4jOrderRepository(OrderRepository):
    def __init__(self, db: Neo4jDatabase):
        self.db = db

    @staticmethod
    def _order(row) -> Order:
        o = row["o"]
        return Order(
            id=o["id"],
            customer_id=row["customer_id"],
            event_date=_native(o["event_date"]),
            guest_count=o["guest_count"],
            delivery_address=o["delivery_address"],
            lines=[
                OrderLine(l["dish_id"], l["dish_name"], l["unit_price_nok"], l["quantity"],
                          list(l["allergens"]))
                for l in row["lines"]
            ],
            guest_groups=[GuestGroup(g["name"], g["count"], g["notes"]) for g in row["groups"]],
            status=o["status"],
            payment_status=o["payment_status"],
            created_at=_native(o["created_at"]),
            customer_name=row["customer_name"],
        )

    _MATCH = "MATCH (u:User)-[:PLACED]->(o:Order) "

    def get(self, order_id):
        rows = self.db.run(self._MATCH + "WHERE o.id = $id" + _ORDER_RETURN, id=order_id)
        return self._order(rows[0]) if rows else None

    def list_for_customer(self, customer_id):
        rows = self.db.run(
            self._MATCH + "WHERE u.id = $customer_id" + _ORDER_RETURN
            + "ORDER BY o.event_date DESC, o.id DESC",
            customer_id=customer_id,
        )
        return [self._order(r) for r in rows]

    def list_filtered(self, status=None, date_from=None, date_to=None):
        clauses = []
        if status:
            clauses.append("o.status = $status")
        if date_from:
            clauses.append("o.event_date >= $date_from")
        if date_to:
            clauses.append("o.event_date <= $date_to")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.db.run(
            self._MATCH + where + _ORDER_RETURN + "ORDER BY o.event_date, o.id",
            status=status, date_from=date_from, date_to=date_to,
        )
        return [self._order(r) for r in rows]

    def add(self, order):
        def work(tx):
            new_id = tx.run(
                "MATCH (u:User {id: $customer_id}) " + NEXT_ID
                + "MATCH (u:User {id: $customer_id}) "
                "CREATE (u)-[:PLACED]->(o:Order {id: new_id, event_date: $event_date,"
                " guest_count: $guest_count, delivery_address: $delivery_address,"
                " status: $status, payment_status: $payment_status, created_at: $created_at})"
                " RETURN o.id AS id",
                label="Order", customer_id=order.customer_id, event_date=order.event_date,
                guest_count=order.guest_count, delivery_address=order.delivery_address,
                status=order.status, payment_status=order.payment_status,
                created_at=_seconds(order.created_at),
            ).single()["id"]
            tx.run(
                "MATCH (o:Order {id: $id}) UNWIND $lines AS line "
                "CREATE (o)-[:HAS_LINE]->(l:OrderLine) SET l = line "
                "WITH l OPTIONAL MATCH (d:Dish {id: l.dish_id}) "
                "FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END |"
                " CREATE (l)-[:OF_DISH]->(d))",
                id=new_id,
                lines=[
                    {"pos": i, "dish_id": l.dish_id, "dish_name": l.dish_name,
                     "unit_price_nok": l.unit_price_nok, "quantity": l.quantity,
                     "allergens": list(l.allergens)}
                    for i, l in enumerate(order.lines)
                ],
            )
            tx.run(
                "MATCH (o:Order {id: $id}) UNWIND $groups AS grp "
                "CREATE (o)-[:HAS_GROUP]->(g:GuestGroup) SET g = grp",
                id=new_id,
                groups=[
                    {"pos": i, "name": g.name, "count": g.count, "notes": g.notes}
                    for i, g in enumerate(order.guest_groups)
                ],
            )
            return new_id

        order.id = self.db.write(work)
        return order

    def update_status(self, order_id, status, payment_status):
        self.db.run(
            "MATCH (o:Order {id: $id}) SET o.status = $status, o.payment_status = $payment_status",
            id=order_id, status=status, payment_status=payment_status,
        )

    def guests_on_date(self, event_date):
        rows = self.db.run(
            "MATCH (o:Order {event_date: $day}) WHERE NOT o.status IN $inactive "
            "RETURN coalesce(sum(o.guest_count), 0) AS n",
            day=event_date, inactive=[OrderStatus.REJECTED, OrderStatus.CANCELLED],
        )
        return rows[0]["n"]


_QUESTION_MATCH = """
MATCH (asker:User)-[:ASKED]->(q:Question)-[:ABOUT]->(o:Order)
OPTIONAL MATCH (admin:User)-[:ANSWERED]->(q)
"""
_QUESTION_RETURN = " RETURN q, o.id AS order_id, asker.id AS customer_id, admin.id AS answered_by "


class Neo4jQuestionRepository(QuestionRepository):
    def __init__(self, db: Neo4jDatabase):
        self.db = db

    @staticmethod
    def _question(row) -> Question:
        q = row["q"]
        return Question(
            id=q["id"],
            order_id=row["order_id"],
            customer_id=row["customer_id"],
            body=q["body"],
            created_at=_native(q["created_at"]),
            answer=q.get("answer"),
            answered_at=_native(q.get("answered_at")),
            answered_by=row["answered_by"],
        )

    def get(self, question_id):
        rows = self.db.run(
            _QUESTION_MATCH + "WITH * WHERE q.id = $id" + _QUESTION_RETURN, id=question_id
        )
        return self._question(rows[0]) if rows else None

    def list_for_order(self, order_id):
        rows = self.db.run(
            _QUESTION_MATCH + "WITH * WHERE o.id = $order_id" + _QUESTION_RETURN
            + "ORDER BY q.created_at, q.id",
            order_id=order_id,
        )
        return [self._question(r) for r in rows]

    def list_all(self, unanswered_only=False):
        where = "WITH * WHERE q.answer IS NULL" if unanswered_only else ""
        rows = self.db.run(
            _QUESTION_MATCH + where + _QUESTION_RETURN + "ORDER BY q.created_at DESC, q.id DESC"
        )
        return [self._question(r) for r in rows]

    def add(self, question):
        rows = self.db.run(
            "MATCH (o:Order {id: $order_id}), (u:User {id: $customer_id}) " + NEXT_ID
            + "MATCH (o:Order {id: $order_id}), (u:User {id: $customer_id}) "
            "CREATE (u)-[:ASKED]->(q:Question {id: new_id, body: $body,"
            " created_at: $created_at})-[:ABOUT]->(o) RETURN q.id AS id",
            label="Question", order_id=question.order_id, customer_id=question.customer_id,
            body=question.body, created_at=_seconds(question.created_at),
        )
        question.id = rows[0]["id"]
        return question

    def answer(self, question_id, answer, admin_id):
        self.db.run(
            "MATCH (q:Question {id: $id}), (admin:User {id: $admin_id}) "
            "OPTIONAL MATCH (:User)-[old:ANSWERED]->(q) DELETE old "
            "WITH DISTINCT q, admin "
            "SET q.answer = $answer, q.answered_at = $answered_at "
            "CREATE (admin)-[:ANSWERED]->(q)",
            id=question_id, admin_id=admin_id, answer=answer,
            answered_at=_seconds(datetime.now()),
        )
