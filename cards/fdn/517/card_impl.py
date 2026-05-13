"""Card implementation for CemeteryRecruitment."""

from __future__ import annotations


from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, TargetRequirement, Zone
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
    # Real pipeline: targets stored by cast_spell on the card
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    # Test backdoor: attribute set directly by test code
    return getattr(card, "_resolve_target", None)


class CemeteryRecruitment(Sorcery):
    """Cemetery Recruitment — {1}{B} — Return target creature card from graveyard to hand.

    The Zombie bonus draw is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cemetery Recruitment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Return target creature card from your graveyard to your hand. "
            "If it's a Zombie card, draw a card.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast if no creature cards in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return False
        graveyard = game.get_graveyard(controller)
        for obj in graveyard.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature card in your graveyard."""
        controller = self.controller
        if controller is None:
            return []

        targets: list[Any] = []
        graveyard = game.get_graveyard(controller)
        for obj in graveyard.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                targets.append(obj)

        if not targets:
            return []

        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "owner", None) is _c
                ),
                description="target creature card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Return the target creature card from graveyard to hand."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        controller = self.controller
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        hand = game.get_hand(controller)

        if graveyard.contains(target):
            graveyard.remove(target)
            hand.add(target)


__all__ = ["CemeteryRecruitment"]
