"""Card implementation for Pestbrood Sloth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, CreatureDiesTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PestbroodSloth(Creature):
    """Pestbrood Sloth — {3}{G} — 4/4 Creature — Plant Sloth.

    Reach.
    When this creature dies, create two 1/1 black and green Pest creature
    tokens with "Whenever this token attacks, you gain 1 life."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pestbrood Sloth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Plant", "Sloth"})
        kwargs.setdefault("keywords", Keyword.REACH)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the dies trigger."""
        controller = self.controller

        def _condition(g: "GameState", event: CreatureDiesTriggeredEvent) -> bool:
            return event.creature is self

        def _effect(g: "GameState") -> None:
            owner = self.controller
            for _ in range(2):
                pest = _PestToken(owner=owner, controller=owner)
                g.get_battlefield(owner).add(pest)
                pest.register_triggers(g)

        game.trigger_manager.register(TriggerRegistration(
            event_type=CreatureDiesTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


class _PestToken(Creature):
    """1/1 black and green Pest creature token with attack life gain."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest")
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Pest"})
        super().__init__(**kwargs)
        self.is_token = True

    def register_triggers(self, game: "GameState") -> None:
        """Register 'Whenever this attacks, you gain 1 life.'"""
        controller = self.controller

        def _condition(g: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is self or event.attacker is self

        def _effect(g: "GameState") -> None:
            owner = self.controller
            owner.life += 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
