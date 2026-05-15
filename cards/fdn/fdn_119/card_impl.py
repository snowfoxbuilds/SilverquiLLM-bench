"""Card implementation for Elenda, Saint of Dusk."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class ElendaSaintOfDusk(Creature):
    """Elenda, Saint of Dusk — {2}{W}{B} — 4/4 — Legendary Vampire Knight.

    Lifelink, hexproof from instants
    As long as your life total is greater than your starting life total,
    Elenda gets +1/+1 and has menace. Elenda gets an additional +5/+5 as
    long as your life total is at least 10 greater than your starting life
    total.

    FDN collector number 119.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elenda, Saint of Dusk")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Knight"})
        kwargs.setdefault("supertypes", {"Legendary"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Lifelink, hexproof from instants\n"
            "As long as your life total is greater than your starting life "
            "total, Elenda gets +1/+1 and has menace. Elenda gets an "
            "additional +5/+5 as long as your life total is at least 10 "
            "greater than your starting life total.",
        )
        super().__init__(**kwargs)
        self._life_effect_ref: ContinuousEffect | None = None
        # ENGINE LIMITATION: hexproof from instants not fully modeled;
        # using general hexproof approximation flag
        self._hexproof_from_instants = True

    def register_triggers(self, game: "GameState") -> None:
        """Register continuous effect for life-based P/T boost."""
        source = self

        def _apply_life_bonus(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            if not _is_on_battlefield(game, source):
                return
            starting_life = getattr(ctrl, "starting_life", 20)
            current_life = getattr(ctrl, "life", 20)
            if current_life > starting_life:
                source.base_power += 1
                source.base_toughness += 1
                source.keywords = (
                    getattr(source, "keywords", None) or Keyword(0)
                ) | Keyword.MENACE
            if current_life >= starting_life + 10:
                source.base_power += 5
                source.base_toughness += 5

        self._life_effect_ref = game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_life_bonus,
            duration=DURATION_PERMANENT,
        ))

    def unregister_triggers(self, game: "GameState") -> None:
        """Clean up continuous effect when leaving battlefield."""
        if self._life_effect_ref is not None:
            game.effect_manager.remove(self._life_effect_ref)
            self._life_effect_ref = None
