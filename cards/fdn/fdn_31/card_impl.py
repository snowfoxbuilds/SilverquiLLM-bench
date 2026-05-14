"""Card implementation for Bigfin Bouncer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BigfinBouncer(Creature):
    """Bigfin Bouncer — {3}{U} — 3/2 — Shark Pirate.

    When this creature enters, return target creature an opponent controls
    to its owner's hand.

    FDN collector number 31.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bigfin Bouncer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Shark", "Pirate"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target creature an opponent "
            "controls to its owner's hand.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Choose target creature an opponent controls to bounce."""
        controller = self.controller
        if controller is None:
            return []
        targets: list = []
        for player in game.players:
            if player is controller:
                continue
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                from engine.types import CardType
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE in card_types:
                    targets.append(obj)
        if not targets:
            return []
        # Controller chooses one target
        chosen = controller.choose_target(targets, "creature an opponent controls") if hasattr(controller, "choose_target") else targets[0]
        return [chosen] if chosen else []

    def on_resolve(self, game: "GameState") -> None:
        """ETB: bounce target creature an opponent controls."""
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # Get chosen target (lazy revalidation at resolution)
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else getattr(self, "_resolve_target", None)
        if target is None:
            return

        # Verify target is still on an opponent's battlefield
        for player in game.players:
            if player is controller:
                continue
            bf = game.get_battlefield(player)
            if bf.contains(target):
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
                return
