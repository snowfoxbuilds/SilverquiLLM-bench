from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class EruditeWizard(Creature):
    """Erudite Wizard."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Erudite Wizard")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Wizard"}
        super().__init__(**kwargs)
