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

    Flying, vigilance.  Each instant and sorcery spell you cast has casualty 1
    (you may sacrifice a creature with power >= 1 to copy the spell).

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Grant casualty 1 to the controller's instant and sorcery spells."""
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        dragon = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            if event.controller is not dragon.controller:
                return False
            card = event.card
            if card is dragon:
                return False
            types = getattr(card, "card_types", set())
            if not (types & {CardType.INSTANT, CardType.SORCERY}):
                return False
            # Stash the StackObject so the effect (which only receives game)
            # can find the spell to copy.
            dragon._casualty_spell = event.spell
            return True

        def _effect(game: Any) -> None:
            from engine.game import sacrifice

            ctrl = dragon.controller
            if ctrl is None:
                return
            spell = getattr(dragon, "_casualty_spell", None)
            if spell is None:
                return
            eligible = [
                obj for obj in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "power", 0) >= 1
            ]
            if not eligible:
                return
            if not ctrl.choose_yes_no("Casualty 1: sacrifice a creature to copy?"):
                return
            creature = ctrl.choose_card(eligible, "Choose a creature to sacrifice")
            if creature is None:
                return
            sacrifice(game, ctrl, creature)
            game.stack.push(copy_spell(game, spell, ctrl, new_targets=list(spell.targets)))

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
