"""Card implementation for Felidar Savior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class FelidarSavior(Creature):
    """Felidar Savior — {3}{W} — 2/3 — Cat Beast — Lifelink.

    When this creature enters, put a +1/+1 counter on each of up to two
    other target creatures you control.

    FDN collector number 12.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Felidar Savior")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Beast"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Lifelink\nWhen this creature enters, put a +1/+1 counter on "
            "each of up to two other target creatures you control.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return targeting requirement: up to two other creatures you control."""
        controller = self.controller or getattr(self, "owner", None)
        source = self

        def _filter(obj: Any) -> bool:
            if obj is source:
                return False
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            return getattr(obj, "controller", None) is controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="first of up to two other target creatures you control",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=_filter,
                description="second of up to two other target creatures you control",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: put a +1/+1 counter on each of up to two other target
        creatures you control."""
        from engine.game import add_counter

        controller = self.controller
        if controller is None:
            return

        # Get targets from chosen_targets (set by StackObject.targets)
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        for target in chosen[:2]:
            if target is self:
                continue
            if not _is_on_battlefield(game, target):
                continue
            if getattr(target, "controller", None) is not controller:
                continue
            add_counter(game, target, "+1/+1", 1)
            # Sync original counters
