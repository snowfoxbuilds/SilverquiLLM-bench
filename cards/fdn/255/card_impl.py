"""Card implementation for Juggernaut."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import ManaCost


class Juggernaut(ArtifactCreature):
    """Juggernaut — {4} — 5/3. Attacks each combat if able. Can't be blocked by Walls."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Juggernaut")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Juggernaut"}
        kwargs.setdefault(
            "rules_text",
            "This creature attacks each combat if able.\n"
            "This creature can't be blocked by Walls.",
        )
        super().__init__(**kwargs)
        self.must_attack = True
        self.cant_be_blocked_by_walls = True
