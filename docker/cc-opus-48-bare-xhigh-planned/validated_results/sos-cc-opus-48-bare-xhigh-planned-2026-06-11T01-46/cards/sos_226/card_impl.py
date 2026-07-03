"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 Legendary Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.  (As you cast that
    spell, you may sacrifice a creature with power 1 or greater.  When you do,
    copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["keywords"] = (kwargs.get("keywords") or Keyword(0)) | Keyword.FLYING | Keyword.VIGILANCE
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1. (As you cast that spell, you may sacrifice a creature "
            "with power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Grant casualty 1 to instant/sorcery spells this controller casts."""
        from engine.triggers import TriggerRegistration
        from engine.events import SpellCastTriggeredEvent

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            ctrl = source.controller
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl or ctrl is None:
                return False
            if not g.get_battlefield(ctrl).contains(source):
                return False
            spell_obj = getattr(event, "spell", None)
            card = getattr(spell_obj, "source", None) or getattr(event, "card", None)
            if card is None or not (getattr(card, "card_types", set()) & _SPELL_TYPES):
                return False
            source._casualty_so = spell_obj
            return True

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            spell_obj = getattr(source, "_casualty_so", None)
            if spell_obj is None:
                return
            candidates = [
                c for c in g.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return
            # Casualty 1 is a "may": choose a creature to sacrifice, or decline.
            chosen = ctrl.choose_card(
                candidates, "Casualty 1: sacrifice a creature with power 1+ (or decline)"
            )
            if chosen is None or getattr(chosen, "power", 0) < 1:
                return
            from engine.game import sacrifice
            sacrifice(g, ctrl, chosen)
            # Copy the spell above the original; keeps the original's targets
            # (declining to choose new targets is always legal).
            from engine.stack import copy_spell
            g.stack.push(copy_spell(g, spell_obj, ctrl))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=getattr(self, "controller", None) or game.active_player,
            )
        )
