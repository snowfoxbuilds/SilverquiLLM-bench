"""Card implementation for Bigfin Bouncer (FDN #15 slot).

Demonstrates a targeted ETB trigger: when this creature enters the
battlefield, return target creature an opponent controls to its owner's hand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BigfinBouncer(Creature):
    """Bigfin Bouncer — {3}{U} — 3/2 — Merfolk Rogue.

    When this creature enters, return target creature an opponent
    controls to its owner's hand.

    FDN collector number 15 (reference slot for targeted ETB).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bigfin Bouncer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Rogue"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target creature an opponent "
            "controls to its owner's hand.",
        )
        super().__init__(**kwargs)
        # Target is selected during ETB trigger resolution.
        self.chosen_targets: list[Any] = []

    def on_resolve(self, game: "GameState") -> None:
        """ETB: return target opponent's creature to its owner's hand.

        Target validation: the target must be on an opponent's battlefield.
        If the target is no longer valid (left the battlefield), the
        ability fizzles (does nothing).
        """
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        if not self.chosen_targets:
            return

        target = self.chosen_targets[0]

        # Validate target: must be on an opponent's battlefield
        for player in game.players:
            if player is controller:
                continue
            bf = game.get_battlefield(player)
            if target in bf.get_all():
                # Valid target — bounce it to owner's hand
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
                return

        # Target not found on any opponent's battlefield — fizzles
