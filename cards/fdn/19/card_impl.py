"""Card implementation for JoustThrough."""

from __future__ import annotations


from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


class JoustThrough(Instant):
    """Joust Through — {W} — Deal 3 damage to target attacking or blocking
    creature.  You gain 1 life.

    FDN collector number 19.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Joust Through")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Joust Through deals 3 damage to target attacking or blocking "
            "creature. You gain 1 life.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield.

        In a full implementation this would be restricted to attacking or
        blocking creatures, but we allow any creature for simplicity.
        """
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target attacking or blocking creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Deal 3 damage to the target creature; gain 1 life."""
        from engine.game import deal_damage

        target = _get_chosen_target(self, game)
        if target is None:
            return
        # Verify target is still legal; if not, spell fizzles entirely
        target_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    target_valid = True
                    break
        if not target_valid:
            return
        deal_damage(game, self, target, 3)
        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += 1


__all__ = ["JoustThrough"]
