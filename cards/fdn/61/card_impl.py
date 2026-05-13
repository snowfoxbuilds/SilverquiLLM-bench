"""Card implementation for High-Society Hunter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.game import draw_card, sacrifice
from engine.triggers import EventType, TriggerRegistration
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class HighSocietyHunter(Creature):
    """High-Society Hunter — {3}{B}{B} — 5/3 — Vampire Noble — Flying

    Whenever this creature attacks, you may sacrifice another creature.
    If you do, put a +1/+1 counter on this creature.
    Whenever another nontoken creature dies, draw a card.

    FDN collector number 61.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "High-Society Hunter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Noble"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhenever this creature attacks, you may sacrifice "
            "another creature. If you do, put a +1/+1 counter on this "
            "creature.\nWhenever another nontoken creature dies, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _dies_condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is source:
                return False  # "another" — not self
            if getattr(creature, "is_token", False):
                return False  # nontoken only
            return True

        def _dies_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is not None:
                draw_card(game, controller)

        # ENGINE LIMITATION: Attack trigger with sacrifice choice not
        # implemented. Would need: prompt player to sacrifice another
        # creature, if they do add +1/+1 counter.

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))
