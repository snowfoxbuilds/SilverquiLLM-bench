"""Card implementation for Living History."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment, Creature
from engine.events import EntersBattlefieldTriggeredEvent, AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class LivingHistory(Enchantment):
    """Living History — {1}{R} — Enchantment.

    When this enchantment enters, create a 2/2 red and white Spirit creature token.
    Whenever you attack, if a card left your graveyard this turn, target attacking
    creature gets +2/+0 until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Living History")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: create a 2/2 red and white Spirit creature token."""
        self._create_spirit_token(game)

    def _create_spirit_token(self, game: "GameState") -> None:
        """Create a 2/2 red and white Spirit creature token."""
        controller = self.controller
        token = Creature(
            name="Spirit",
            base_power=2,
            base_toughness=2,
            owner=controller,
            controller=controller,
            subtypes={"Spirit"},
        )
        token.is_token = True
        token.colors = {"R", "W"}
        bf = game.get_battlefield(controller)
        bf.add(token)

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger."""
        controller = self.controller

        def condition(g: "GameState", event: Any) -> bool:
            # Fire when any creature controlled by this card's controller attacks
            creature = event.creature
            return getattr(creature, "controller", None) is controller

        def effect(g: "GameState") -> None:
            # If a card left controller's graveyard this turn, give +2/+0 to an attacking creature
            if not g.card_left_graveyard_this_turn(controller):
                return
            # Find an attacking creature we control
            bf = g.get_battlefield(controller)
            for obj in bf.get_all():
                if getattr(obj, "is_attacking", False) and getattr(obj, "controller", None) is controller:
                    # Give +2/+0
                    bonus = getattr(obj, "_temp_power_bonus", 0)
                    obj._temp_power_bonus = bonus + 2
                    break

        trigger = TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=condition,
            effect=effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)
