"""Card implementation for Sure Strike."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Instant, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

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

class SureStrike(Instant):
    """Sure Strike — {1}{R} — Target creature gets +3/+0 and gains
    first strike until end of turn.

    FDN collector number 209.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sure Strike")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature gets +3/+0 and gains first strike until "
            "end of turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Apply +3/+0 and first strike until end of turn."""
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

        def _apply_buff(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.modified_power += 3
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.FIRST_STRIKE
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_buff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
