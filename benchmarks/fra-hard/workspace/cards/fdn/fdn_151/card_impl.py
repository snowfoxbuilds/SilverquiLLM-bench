"""Card implementation for Aetherize."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Aetherize(Instant):
    """Aetherize — {3}{U} — Instant.

    Return all attacking creatures to their owner's hand.

    FDN collector number 151.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Aetherize")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Return all attacking creatures to their owner's hand.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Return all attacking creatures to their owner's hand."""
        from engine.zones import move_to_zone

        attackers = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    if getattr(obj, "is_attacking", False) or getattr(obj, "attacking", False):
                        attackers.append(obj)
        for attacker in attackers:
            move_to_zone(game, attacker, Zone.BATTLEFIELD, Zone.HAND)
