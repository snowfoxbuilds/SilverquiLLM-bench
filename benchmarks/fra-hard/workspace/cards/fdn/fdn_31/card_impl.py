"""Card implementation for Bigfin Bouncer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

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

    def _is_opponent_creature(self, obj: Any) -> bool:
        """Legal target: a creature controlled by a player other than me."""
        if CardType.CREATURE not in getattr(obj, "card_types", set()):
            return False
        obj_controller = getattr(obj, "controller", None)
        return obj_controller is not None and obj_controller is not self.controller

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature an opponent controls (chosen at cast/ETB)."""
        return [
            TargetRequirement(
                filter_fn=self._is_opponent_creature,
                description="target creature an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: bounce the chosen creature to its owner's hand.

        Revalidate the COMPLETE target predicate at resolution (rule 608.2b):
        the target must still be a creature an opponent controls, on the
        battlefield — not merely still on *a* battlefield. If it changed control
        to the caster, left play, or ceased to be a creature, it is illegal and
        the ETB does nothing.
        """
        from engine.zones import move_to_zone

        targets = getattr(self, "chosen_targets", None) or []
        target = targets[0] if targets else None
        if target is None:
            return
        on_bf = any(game.get_battlefield(p).contains(target) for p in game.players)
        if not on_bf or not self._is_opponent_creature(target):
            return
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
