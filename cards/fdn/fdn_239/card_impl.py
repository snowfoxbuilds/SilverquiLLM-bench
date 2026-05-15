"""Card implementation for Empyrean Eagle."""

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
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class EmpyreanEagle(Creature):
    """Empyrean Eagle — {1}{W}{U} — 2/3 — Bird Spirit.

    Flying
    Other creatures you control with flying get +1/+1.

    FDN collector number 239.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Empyrean Eagle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{U}"))
        kwargs.setdefault("subtypes", {"Bird", "Spirit"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nOther creatures you control with flying get +1/+1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register lord effect for flying creatures."""
        source = self

        def _apply_lord(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or not _is_on_battlefield(game, source):
                return
            bf = game.get_battlefield(ctrl)
            for obj in bf.get_all():
                if obj is source:
                    continue
                if CardType.CREATURE not in getattr(obj, "card_types", set()):
                    continue
                kw = getattr(obj, "keywords", Keyword(0))
                if kw & Keyword.FLYING:
                    obj.base_power += 1
                    obj.base_toughness += 1

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_lord,
            duration=DURATION_PERMANENT,
        ))
