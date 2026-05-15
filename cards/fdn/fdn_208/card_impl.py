"""Card implementation for Spitfire Lagac."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SpitfireLagac(Creature):
    """Spitfire Lagac — {3}{R} — 3/4 — Lizard.

    Landfall — Whenever a land you control enters, this creature deals
    1 damage to each opponent.

    FDN collector number 208.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spitfire Lagac")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("subtypes", {"Lizard"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Landfall — Whenever a land you control enters, this creature "
            "deals 1 damage to each opponent.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register landfall trigger for damage."""
        from engine.game import deal_damage
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _landfall_condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            permanent = data.get("permanent")
            if permanent is None:
                return False
            card_types = getattr(permanent, "card_types", set())
            if CardType.LAND not in card_types:
                return False
            perm_ctrl = getattr(permanent, "controller", None)
            if perm_ctrl is None:
                bf = game.get_battlefield(ctrl)
                return bf.contains(permanent)
            return perm_ctrl is ctrl

        def _landfall_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            for player in game.players:
                if player is not ctrl:
                    deal_damage(game, source, player, 1)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_landfall_condition,
            effect=_landfall_effect,
            source=self,
            controller=controller,
        ))
