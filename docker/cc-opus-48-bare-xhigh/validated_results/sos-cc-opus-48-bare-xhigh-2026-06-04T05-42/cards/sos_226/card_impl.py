"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 Legendary Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1. (As you cast
    it, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance.\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        super().__init__(**kwargs)
        self.colors = ["B", "W"]

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: SpellCastTriggeredEvent) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None or event.controller is not controller:
                return False
            card = event.card
            if card is None or card is source:
                return False
            types = getattr(card, "card_types", set())
            return CardType.INSTANT in types or CardType.SORCERY in types

        def _effect(g: "GameState", event: SpellCastTriggeredEvent) -> None:
            from engine.game import sacrifice
            from engine.player import ScriptExhaustedError
            from engine.stack import copy_spell

            controller = getattr(source, "controller", None)
            if controller is None:
                return
            candidates = [
                obj
                for obj in g.get_battlefield(controller).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "power", 0) >= 1
            ]
            if not candidates:
                return
            try:
                if not controller.choose_yes_no("casualty 1: sacrifice a creature?"):
                    return
            except (ScriptExhaustedError, NotImplementedError):
                return
            try:
                chosen = controller.choose_card(candidates, "casualty: sacrifice")
            except (ScriptExhaustedError, NotImplementedError):
                chosen = candidates[0]
            if chosen is None or not g.get_battlefield(controller).contains(chosen):
                return
            sacrifice(g, controller, chosen)
            spell_obj = event.spell
            if spell_obj is None:
                return
            copy_obj = copy_spell(g, spell_obj, controller)
            g.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )
