from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class DayOfJudgment(Sorcery):
    """Day of Judgment."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Day of Judgment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{W}"))
        super().__init__(**kwargs)
