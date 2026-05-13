from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class SelfReflection(Sorcery):
    """Self-Reflection."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Self-Reflection")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        super().__init__(**kwargs)
