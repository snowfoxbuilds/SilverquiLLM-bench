"""Card implementation for Duel Tactics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class DuelTactics(Sorcery):
    """Duel Tactics — {R} — Sorcery.

    Duel Tactics deals 1 damage to target creature. It can't block this turn.
    Flashback {1}{R}
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Duel Tactics")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault("keywords", Keyword.FLASHBACK)
        kwargs.setdefault(
            "rules_text",
            "Duel Tactics deals 1 damage to target creature. It can't block this turn.\n"
            "Flashback {1}{R}",
        )
        super().__init__(**kwargs)
        self.flashback_cost: ManaCost = ManaCost.parse("{1}{R}")
        self.cast_with_flashback: bool = False

    def can_cast_from_graveyard(self, game: "GameState") -> bool:
        """This card can be cast from the graveyard via flashback."""
        return self.zone == Zone.GRAVEYARD

    def on_resolve(self, game: "GameState") -> None:
        """Deal 1 damage to target creature. It can't block this turn."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # Deal 1 damage
        if hasattr(target, "damage_marked"):
            target.damage_marked += 1

        # Can't block this turn
        target.can_block = False

        # If cast with flashback, exile instead of going to graveyard
        if getattr(self, "cast_with_flashback", False):
            self.zone = Zone.EXILE
