"""Card implementation for Skyship Buccaneer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SkyshipBuccaneer(Creature):
    """Skyship Buccaneer — {3}{U}{U} — 4/3 — Human Pirate — Flying.

    Raid — When this creature enters, if you attacked this turn, draw a card.

    FDN collector number 50.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Skyship Buccaneer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Pirate"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nRaid — When this creature enters, if you attacked "
            "this turn, draw a card.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: Raid — if you attacked this turn, draw a card."""
        from engine.game import draw_card

        controller = self.controller
        if controller is None:
            return

        # Check if controller attacked this turn
        attacked_this_turn = getattr(game, "attacked_this_turn", False)
        # Also check combat state for attackers declared by this player
        if not attacked_this_turn:
            combat = getattr(game, "combat", None)
            if combat is not None:
                attackers = getattr(combat, "attackers", [])
                for attacker in attackers:
                    if getattr(attacker, "controller", None) is controller:
                        attacked_this_turn = True
                        break
        # Also check player-level tracking
        if not attacked_this_turn:
            attacked_this_turn = getattr(controller, "attacked_this_turn", False)

        if attacked_this_turn:
            draw_card(game, controller)
