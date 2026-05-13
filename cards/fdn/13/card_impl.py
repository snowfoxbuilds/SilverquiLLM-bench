"""Card implementation for Fleeting Flight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ContinuousEffect, Instant
from engine.continuous_effects import Layer
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState




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
class FleetingFlight(Instant):
    """Fleeting Flight — {W} — Put a +1/+1 counter on target creature.
    It gains flying until end of turn. Prevent all combat damage that
    would be dealt to it this turn.

    (Prevention shield not fully implemented.)

    FDN collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fleeting Flight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on target creature. It gains flying "
            "until end of turn. Prevent all combat damage that would be "
            "dealt to it this turn.",
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
        """Put +1/+1 counter; grant flying until EOT."""
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

        # +1/+1 counter via plus_one_counters (not base_power mutation)
        if hasattr(target, "plus_one_counters"):
            target.plus_one_counters += 1
            target._original_plus_one_counters = target.plus_one_counters  # type: ignore[attr-defined]

        creature_ref = target

        def _apply_flying(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.FLYING
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_flying,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
