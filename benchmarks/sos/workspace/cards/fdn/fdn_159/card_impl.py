"""Card implementation for Mocking Sprite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class MockingSprite(Creature):
    """Mocking Sprite — {2}{U} — 2/1 — Faerie Rogue — Flying.

    Instant and sorcery spells you cast cost {1} less to cast.

    FDN collector number 159.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mocking Sprite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Faerie", "Rogue"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flying\nInstant and sorcery spells you cast cost {1} less to cast.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register cost reduction continuous effect."""
        source = self

        # ENGINE LIMITATION: Cost reduction for other spells is best modeled
        # via cost_reduction() on those spells or a game-level hook. We store
        # a flag that can be checked by the casting system.
        source._provides_cost_reduction = True

    def apply_continuous_effect(self, game: "GameState") -> None:
        """Register continuous effect for spell cost reduction."""
        source = self

        def _apply(game: Any) -> None:
            # ENGINE LIMITATION: The engine doesn't have a central cost
            # reduction registry. This effect is a marker that the casting
            # system would consult.
            pass

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITIES,
            sublayer=SubLayer.ADD_ABILITY,
            apply=_apply,
            duration=DURATION_PERMANENT,
        ))
