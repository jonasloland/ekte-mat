"""Handlekurv-logikk. Kurven lagres som {dish_id: antall} i Flask-sesjonen;
denne klassen eier reglene (minstebestilling, totalpris)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.entities import Dish
from app.models.repositories.base import DishRepository


class CartError(ValueError):
    pass


@dataclass
class CartItem:
    dish: Dish
    quantity: int

    @property
    def subtotal_nok(self) -> int:
        return self.dish.price_nok * self.quantity


class Cart:
    def __init__(self, data: dict, dishes: DishRepository):
        # Sesjonen serialiserer nøkler som strenger
        self._data: dict[str, int] = {str(k): int(v) for k, v in data.items()}
        self._dishes = dishes

    def to_dict(self) -> dict[str, int]:
        return dict(self._data)

    def _published_dish(self, dish_id: int) -> Dish:
        dish = self._dishes.get(dish_id)
        if dish is None or not dish.published:
            raise CartError("Retten finnes ikke.")
        return dish

    def set_quantity(self, dish_id: int, quantity: int) -> None:
        """Setter antall. 0 fjerner retten. Avviser antall under minstebestilling."""
        if quantity <= 0:
            self.remove(dish_id)
            return
        dish = self._published_dish(dish_id)
        if quantity < dish.min_order:
            raise CartError(
                f"Minstebestilling for «{dish.name}» er {dish.min_order} porsjoner."
            )
        self._data[str(dish_id)] = quantity

    def add(self, dish_id: int, quantity: int) -> None:
        current = self._data.get(str(dish_id), 0)
        self.set_quantity(dish_id, current + quantity)

    def remove(self, dish_id: int) -> None:
        self._data.pop(str(dish_id), None)

    def clear(self) -> None:
        self._data.clear()

    def items(self) -> list[CartItem]:
        """Retter i kurven. Retter som er slettet/avpublisert hoppes over."""
        result = []
        for dish_id, qty in self._data.items():
            dish = self._dishes.get(int(dish_id))
            if dish and dish.published:
                result.append(CartItem(dish, qty))
        return result

    @property
    def total_nok(self) -> int:
        return sum(i.subtotal_nok for i in self.items())

    @property
    def count(self) -> int:
        return sum(self._data.values())

    def is_empty(self) -> bool:
        return not self.items()
