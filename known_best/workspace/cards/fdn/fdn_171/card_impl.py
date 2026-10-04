"""Card implementation for Diregraf Ghoul."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class DiregrafGhoulAbility1:
    text = 'This creature enters tapped.'


# endregion Printed abilities


class DiregrafGhoul(Creature):
    """Diregraf Ghoul — {B} — 2/2 — Zombie.

    This creature enters tapped.

    FDN collector number 171.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Diregraf Ghoul")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "This creature enters tapped.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Enter the battlefield tapped."""
        self.is_tapped = True
