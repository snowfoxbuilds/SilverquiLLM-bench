"""Card implementation for Dazzling Angel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class DazzlingAngel(Creature):
    """Dazzling Angel — {2}{W} — 2/3 — Angel — Flying.

    Whenever another creature you control enters, you gain 1 life.

    FDN collector number 9.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dazzling Angel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Angel"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhenever another creature you control enters, you "
            "gain 1 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register ETB trigger: another creature enters → gain 1 life."""
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _etb_condition(game: Any, data: dict) -> bool:
            """Fire when another creature we control enters."""
            permanent = data.get("permanent")
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, "controller", None)
            if getattr(permanent, "controller", None) is not ctrl:
                return False
            if CardType.CREATURE not in getattr(permanent, "card_types", set()):
                return False
            return True

        def _etb_effect(game: "GameState") -> None:
            """Gain 1 life."""
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            ctrl.life += 1
            # Fire GAINS_LIFE event
            game.trigger_manager.fire_event(
                game,
                EventType.GAINS_LIFE,
                {"player": ctrl, "amount": 1},
            )

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_etb_condition,
            effect=_etb_effect,
            source=self,
            controller=controller,
        ))
