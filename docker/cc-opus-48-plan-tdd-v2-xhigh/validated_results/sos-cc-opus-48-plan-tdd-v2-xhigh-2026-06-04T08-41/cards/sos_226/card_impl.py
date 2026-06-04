"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _power(obj: Any) -> int:
    val = getattr(obj, "modified_power", None)
    if val is None:
        val = getattr(obj, "base_power", 0)
    return val or 0


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 Legendary Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.

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
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: "GameState", e: Any) -> bool:
            if getattr(e, "controller", None) is not source.controller:
                return False
            spell = getattr(e, "spell", None)
            if spell is None or spell is source:
                return False
            return bool(getattr(spell, "card_types", set()) & _INSTANT_SORCERY)

        def _casualty(g: "GameState") -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            spell_obj = g.stack.peek()
            if spell_obj is None:
                return
            spell_card = spell_obj.source
            if not (getattr(spell_card, "card_types", set()) & _INSTANT_SORCERY):
                return

            fodder = [
                obj for obj in g.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and _power(obj) >= 1 and obj is not spell_card
            ]
            if not fodder:
                return
            if not ctrl.choose_yes_no("Pay casualty 1 (sacrifice a creature)?"):
                return
            creature = ctrl.choose_card(fodder, "Choose a creature to sacrifice")
            if creature is None or creature not in fodder:
                return
            sacrifice(g, ctrl, creature)
            copy = copy_spell(g, spell_obj, ctrl, new_targets=None)
            g.stack.push(copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_casualty,
                source=self,
                controller=controller,
            )
        )
