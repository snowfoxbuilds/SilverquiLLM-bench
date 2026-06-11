"""Card implementation for Tome Blast."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TomeBlast(Sorcery):
    """Tome Blast — {1}{R} — Sorcery.

    Tome Blast deals 2 damage to any target.
    Flashback {4}{R}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tome Blast")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("keywords", Keyword.FLASHBACK)
        kwargs.setdefault(
            "rules_text",
            "Tome Blast deals 2 damage to any target.\n"
            "Flashback {4}{R}",
        )
        super().__init__(**kwargs)
        self.flashback_cost: ManaCost = ManaCost.parse("{4}{R}")
        self.is_flashback_cast: bool = False
        self.chosen_targets: list[Any] = []

    def can_cast_with_flashback(self, game: "GameState") -> bool:
        """Return True if this card can be cast from the graveyard via flashback."""
        return True

    def on_resolve(self, game: "GameState") -> None:
        """Deal 2 damage to the chosen target."""
        targets = getattr(self, "chosen_targets", None)
        if not targets:
            return
        target = targets[0]
        if target is None:
            return
        # Deal 2 damage
        if hasattr(target, "damage_marked"):
            target.damage_marked += 2
        elif hasattr(target, "life"):
            target.life -= 2

        # If cast via flashback, exile
        if self.is_flashback_cast:
            self.zone = Zone.EXILE
            self.exile_on_resolve = True

