"""Card implementation for Inspiring Paladin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
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


class InspiringPaladin(Creature):
    """Inspiring Paladin — {2}{W} — 3/3 — Human Knight.

    During your turn, this creature has first strike.
    During your turn, creatures you control with +1/+1 counters on them
    have first strike.

    FDN collector number 18.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inspiring Paladin")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Knight"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "During your turn, this creature has first strike.\n"
            "During your turn, creatures you control with +1/+1 counters "
            "on them have first strike.",
        )
        super().__init__(**kwargs)
        self._first_strike_effect_ref: ContinuousEffect | None = None

    def register_triggers(self, game: "GameState") -> None:
        """Register continuous effect: during your turn, grant first strike."""
        source = self

        def _apply_first_strike(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or not _is_on_battlefield(game, source):
                return
            # Only during controller's turn
            if game.active_player is not ctrl:
                return
            # Self gets first strike
            source.keywords = source.keywords | Keyword.FIRST_STRIKE
            # Other creatures with +1/+1 counters get first strike
            battlefield = game.get_battlefield(ctrl)
            for obj in battlefield.get_all():
                if obj is source:
                    continue
                if CardType.CREATURE not in getattr(obj, "card_types", set()):
                    continue
                if getattr(obj, "plus_one_counters", 0) > 0:
                    obj.keywords = obj.keywords | Keyword.FIRST_STRIKE

        if self._first_strike_effect_ref is None:
            self._first_strike_effect_ref = game.effect_manager.add(ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_first_strike,
                duration=DURATION_PERMANENT,
            ))
