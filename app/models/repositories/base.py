"""Abstrakte repository-grensesnitt.

Controllere kjenner kun disse grensesnittene. For å bytte til Neo4j (oblig 5)
skriver man nye implementasjoner av disse klassene og endrer fabrikken i
app/models/repositories/__init__.py – controllere og views forblir uendret.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.models.entities import Dish, Order, Question, User


class UserRepository(ABC):
    @abstractmethod
    def get(self, user_id: int) -> Optional[User]: ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    def add(self, user: User) -> User: ...


class DishRepository(ABC):
    @abstractmethod
    def get(self, dish_id: int) -> Optional[Dish]: ...

    @abstractmethod
    def list_all(self) -> list[Dish]: ...

    @abstractmethod
    def list_published(self, event_category: Optional[str] = None) -> list[Dish]: ...

    @abstractmethod
    def add(self, dish: Dish) -> Dish: ...

    @abstractmethod
    def update(self, dish: Dish) -> None: ...

    @abstractmethod
    def delete(self, dish_id: int) -> None: ...


class OrderRepository(ABC):
    @abstractmethod
    def get(self, order_id: int) -> Optional[Order]: ...

    @abstractmethod
    def list_for_customer(self, customer_id: int) -> list[Order]: ...

    @abstractmethod
    def list_filtered(
        self,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list[Order]: ...

    @abstractmethod
    def add(self, order: Order) -> Order: ...

    @abstractmethod
    def update_status(self, order_id: int, status: str, payment_status: str) -> None: ...

    @abstractmethod
    def guests_on_date(self, event_date: date) -> int:
        """Antall gjester i aktive ordrer på en dato (for kapasitetssjekk)."""


class QuestionRepository(ABC):
    @abstractmethod
    def get(self, question_id: int) -> Optional[Question]: ...

    @abstractmethod
    def list_for_order(self, order_id: int) -> list[Question]: ...

    @abstractmethod
    def list_all(self, unanswered_only: bool = False) -> list[Question]: ...

    @abstractmethod
    def add(self, question: Question) -> Question: ...

    @abstractmethod
    def answer(self, question_id: int, answer: str, admin_id: int) -> None: ...


@dataclass
class Repositories:
    """Samler alle repositories, slik at appen kan få dem fra ett sted."""

    users: UserRepository
    dishes: DishRepository
    orders: OrderRepository
    questions: QuestionRepository
