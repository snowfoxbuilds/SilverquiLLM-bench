"""Card implementation for Silverquill, the Disputant (SOS #226)."""

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
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Dragon", "Elder"})
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
        self._casualty_pending: Any = None

    def register_triggers(self, game: "GameState") -> None:
        """Register casualty 1 on each instant/sorcery the controller casts."""
        from engine.triggers import TriggerRegistration

        dragon = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            card = getattr(event, "card", None)
            if card is None:
                return False
            types = getattr(card, "card_types", set())
            if CardType.INSTANT not in types and CardType.SORCERY not in types:
                return False
            if getattr(event, "controller", None) is not dragon.controller:
                return False
            # Stash the triggering spell for the reflexive casualty effect.
            dragon._casualty_pending = getattr(event, "spell", None)
            return True

        def _effect(game: Any) -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            spell = dragon._casualty_pending
            dragon._casualty_pending = None
            ctrl = dragon.controller
            if ctrl is None or spell is None:
                return

            creatures = [
                obj
                for obj in ctrl.zones[Zone.BATTLEFIELD].get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "power", 0) >= 1
            ]
            if not creatures:
                return
            if not ctrl.choose_yes_no(
                "Casualty 1: sacrifice a creature with power 1 or greater?"
            ):
                return
            victim = ctrl.choose_card(creatures, "creature to sacrifice (casualty)")
            if victim is None or victim not in creatures:
                return
            sacrifice(game, ctrl, victim)
            # ENGINE LIMITATION: model the casualty copy as a real spell copy
            # on the stack (same targets); new-target choice is not offered.
            game.stack.push(copy_spell(game, spell, ctrl))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
