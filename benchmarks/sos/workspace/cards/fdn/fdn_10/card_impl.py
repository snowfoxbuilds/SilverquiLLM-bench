"""Card implementation for Divine Resilience."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class DivineResilience(Instant):
    """Divine Resilience — {W} — Instant.

    Kicker {2}{W}
    Target creature you control gains indestructible until end of turn.
    If this spell was kicked, instead any number of target creatures you
    control gain indestructible until end of turn.

    FDN collector number 10.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Divine Resilience")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {2}{W}\n"
            "Target creature you control gains indestructible until end of "
            "turn. If this spell was kicked, instead any number of target "
            "creatures you control gain indestructible until end of turn.",
        )
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse("{2}{W}")

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature(s) you control.

        ENGINE LIMITATION: TargetRequirement does not support variable target
        counts.  When kicked, we return a single requirement; the casting
        pipeline should allow the player to choose any number of creatures
        (the resolve logic handles multiple via ``chosen_targets``).
        """
        controller = self.controller

        def _filter(obj: Any) -> bool:
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            return getattr(obj, "controller", None) is controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description=(
                    "any number of target creatures you control"
                    if self.kicked
                    else "target creature you control"
                ),
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Grant indestructible until end of turn to chosen target(s)."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            t = getattr(self, "_resolve_target", None)
            chosen = [t] if t is not None else []

        if not chosen:
            return

        # If kicked, all chosen targets; otherwise just the first
        targets = chosen if self.kicked else chosen[:1]

        for target in targets:
            if not _is_on_battlefield(game, target):
                continue
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                continue

            creature_ref = target

            def _apply_indestructible(game: Any, _c=creature_ref) -> None:
                if not _is_on_battlefield(game, _c):
                    return
                _c.keywords = getattr(_c, "keywords", Keyword(0)) | Keyword.INDESTRUCTIBLE

            game.effect_manager.add(ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_indestructible,
                duration=DURATION_END_OF_TURN,
            ))
