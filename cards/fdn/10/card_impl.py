"""Card implementation for DivineResilience."""

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


class DivineResilience(Instant):
    """Divine Resilience — {W} — Target creature you control gains
    indestructible until end of turn.

    Kicker {2}{W} not implemented.

    FDN collector number 10.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Divine Resilience")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {2}{W}\nTarget creature you control gains "
            "indestructible until end of turn. If this spell was kicked, "
            "also put two +1/+1 counters on it.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature you control."""
        controller = self.controller
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    if getattr(obj, "controller", None) is controller:
                        targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is _c
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Grant indestructible until end of turn."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        creature_ref = target

        def _apply_indestructible(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.INDESTRUCTIBLE
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_indestructible,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


__all__ = ["DivineResilience"]
