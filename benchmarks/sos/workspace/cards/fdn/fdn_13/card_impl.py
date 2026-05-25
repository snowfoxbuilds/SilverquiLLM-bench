"""Card implementation for Fleeting Flight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class FleetingFlight(Instant):
    """Fleeting Flight — {W} — Instant.

    Put a +1/+1 counter on target creature. It gains flying until end of
    turn. Prevent all combat damage that would be dealt to it this turn.

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

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Put +1/+1 counter, grant flying until EOT, prevent combat damage."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else getattr(self, "_resolve_target", None)
        if target is None:
            return

        if not _is_on_battlefield(game, target):
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        # +1/+1 counter
        from benchmarks.sos.workspace.engine.game import add_counter

        add_counter(game, target, "+1/+1", 1)
        # Sync original counters per KEY_DECISIONS
        if hasattr(target, "_base_plus_one_counters"):
            target._base_plus_one_counters = target.plus_one_counters

        # Flying until end of turn
        creature_ref = target

        def _apply_flying(game: Any) -> None:
            if not _is_on_battlefield(game, creature_ref):
                return
            creature_ref.keywords = getattr(
                creature_ref, "keywords", Keyword(0)
            ) | Keyword.FLYING

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_flying,
            duration=DURATION_END_OF_TURN,
        ))

        # ENGINE LIMITATION: "Prevent all combat damage that would be dealt
        # to it this turn" requires a damage prevention shield / replacement
        # effect, which the engine does not support. The flag is set on the
        # creature but will only work if the combat system checks it.
        creature_ref.combat_damage_prevented = True
