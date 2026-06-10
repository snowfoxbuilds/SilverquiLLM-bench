"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.  (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

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
            "casualty 1. (As you cast that spell, you may sacrifice a creature "
            "with power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            if card is None or not (
                getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
            ):
                return False
            # Remember which spell on the stack this casualty applies to.
            source._casualty_pending = getattr(event, "spell", None)
            return True

        def _effect(g: "GameState") -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = getattr(source, "controller", None)
            spell_obj = getattr(source, "_casualty_pending", None)
            if ctrl is None or spell_obj is None:
                return
            # Casualty 1 — sacrifice a creature with power 1 or greater.
            candidates = [
                c
                for c in ctrl.zones[Zone.BATTLEFIELD].get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return
            # One decision: the creature to sacrifice, or None to decline.
            chosen = ctrl.choose_card(
                candidates, "sacrifice a creature with power 1+ (casualty 1) or decline"
            )
            if chosen is None or chosen not in candidates:
                return
            sacrifice(g, ctrl, chosen)
            # Copy the spell.  New targets default to the original's targets
            # (the "may choose new targets" is optional; keeping them is legal).
            copy_obj = copy_spell(g, spell_obj, ctrl)
            g.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
