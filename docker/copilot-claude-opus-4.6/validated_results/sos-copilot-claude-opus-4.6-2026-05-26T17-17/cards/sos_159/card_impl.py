"""Card implementation for Shopkeeper's Bane."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ShopkeepersBane(Creature):
    """Shopkeeper's Bane — {2}{G} — 4/2 Creature — Badger Pest.

    Trample.
    Whenever this creature attacks, you gain 2 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Shopkeeper's Bane")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Badger", "Pest"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger: gain 2 life."""
        controller = self.controller

        def _condition(g: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is self or event.attacker is self

        def _effect(g: "GameState") -> None:
            owner = self.controller
            owner.life += 2

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
