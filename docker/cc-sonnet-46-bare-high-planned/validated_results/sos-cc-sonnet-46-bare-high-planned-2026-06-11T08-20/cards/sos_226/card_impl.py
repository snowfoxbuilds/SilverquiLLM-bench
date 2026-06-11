"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Elder Dragon 4/4.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
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
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            # Fires for instant/sorcery spells cast by this card's controller
            # while Silverquill is on the battlefield.
            if event.controller is not source.controller:
                return False
            card = event.card
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return

            # Check Silverquill is still on the battlefield.
            bf = g.get_battlefield(ctrl)
            if not bf.contains(source):
                return

            # Find creatures with power >= 1 that can be sacrificed.
            sacrificeable = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not sacrificeable:
                return

            # Player chooses a creature to sacrifice (or None to decline).
            chosen = ctrl.choose_card(sacrificeable, "Casualty 1: sacrifice a creature with power >= 1?")
            if chosen is None:
                return

            # Sacrifice the chosen creature.
            sacrifice(g, ctrl, chosen)

            # Find the spell on the stack to copy (the last pushed instant/sorcery
            # by this controller).
            target_spell = None
            for stack_obj in reversed(g.stack._items):  # noqa: SLF001
                c = stack_obj.source
                c_types = getattr(c, "card_types", set())
                if (CardType.INSTANT in c_types or CardType.SORCERY in c_types) and stack_obj.controller is ctrl:
                    target_spell = stack_obj
                    break

            if target_spell is None:
                return

            # Copy the spell; player may choose new targets for the copy.
            # For simplicity, the copy uses the same targets (new-target-choice
            # requires another prompt which we handle via choose_target scripting
            # if needed — the copy is created with original targets by default).
            copy_obj = copy_spell(g, target_spell, ctrl, new_targets=None)
            # Allow player to retarget the copy if they script new targets.
            # (DeterministicPlayer will pop from script for choose_target calls
            # inside copy_spell if any are needed.)
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
