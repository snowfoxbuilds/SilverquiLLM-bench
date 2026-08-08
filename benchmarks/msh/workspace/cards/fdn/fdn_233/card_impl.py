"""Card implementation for Snakeskin Veil."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
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

class SnakeskinVeil(Instant):
    """Snakeskin Veil — {G} — Put a +1/+1 counter on target creature you
    control. It gains hexproof until end of turn.

    FDN collector number 233.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Snakeskin Veil")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on target creature you control. It "
            "gains hexproof until end of turn.",
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
        """Put a +1/+1 counter on the target; grant hexproof until EOT."""
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

        # +1/+1 counter via the engine primitive (persists across apply_all).
        if hasattr(target, "plus_one_counters"):
            from engine.game import add_counter
            add_counter(game, target, "+1/+1", 1)

        creature_ref = target

        def _apply_hexproof(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.HEXPROOF
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_hexproof,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
