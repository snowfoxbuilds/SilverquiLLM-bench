"""Card implementation for Battlesong Berserker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BattlesongBerserker(Creature):
    """Battlesong Berserker — {3}{R} — 3/4 — Human Berserker.

    Whenever you attack, target creature you control gets +1/+0 and gains
    menace until end of turn.

    FDN collector number 78.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Battlesong Berserker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Berserker"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Whenever you attack, target creature you control gets +1/+0 "
            "and gains menace until end of turn.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger for +1/+0 and menace."""
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, data: dict) -> bool:
            # Fires whenever *you* attack (any creature you control attacks)
            attacker = data.get("creature")
            ctrl = getattr(source, "controller", None)
            return getattr(attacker, "controller", None) is ctrl and ctrl is not None

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            candidates = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
            ]
            if not candidates:
                return
            try:
                chosen = ctrl.choose_card(candidates, "creature to get +1/+0 and menace")
            except Exception:
                chosen = candidates[0]
            if chosen is None:
                return

            def _apply(game: Any) -> None:
                chosen.base_power += 1
                chosen.keywords = (getattr(chosen, "keywords", None) or Keyword(0)) | Keyword.MENACE

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            ))

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ATTACKS,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
