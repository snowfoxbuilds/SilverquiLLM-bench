"""Card implementation for Omniscience."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Enchantment
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
)
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class Omniscience(Enchantment):
    """Omniscience — {7}{U}{U}{U} — Enchantment.

    You may cast spells from your hand without paying their mana costs.

    FDN collector number 161.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Omniscience")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}{U}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "You may cast spells from your hand without paying their mana costs.",
        )
        super().__init__(**kwargs)

    def apply_continuous_effect(self, game: "GameState") -> None:
        """Register continuous effect for free casting."""
        source = self

        def _apply(game: Any) -> None:
            # ENGINE LIMITATION: The engine doesn't have a "cast without
            # paying mana cost" hook. This is a marker effect that the
            # casting system would need to consult.
            if not _is_on_battlefield(game, source):
                return
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl._omniscience_active = True

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        ))
