"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.stack import copy_spell
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant -- {2}{W}{B} Legendary Creature -- Elder Dragon.

    4/4, Flying, Vigilance.

    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1 or
    greater. When you do, copy the spell and you may choose new targets
    for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with "
            "power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Trigger registration -- casualty 1 for instants/sorceries
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register a SpellCastTriggeredEvent trigger that grants casualty 1
        to each instant and sorcery spell the controller casts."""
        # Unregister any previous triggers from this source to avoid duplicates
        # when register_triggers is called multiple times.
        game.trigger_manager.unregister(self)

        controller = self.controller if self.controller is not None else self.owner
        if controller is None:
            return

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            """Only fire for the controller's instant and sorcery spells."""
            if event.controller is not controller:
                return False
            spell_types = getattr(event.spell, "card_types", set())
            return CardType.INSTANT in spell_types or CardType.SORCERY in spell_types

        # The TriggerRegistration effect signature is (game) -> None, so it
        # does not receive the event.  We capture each triggering spell in a
        # FIFO queue so that multiple firings before resolution each get their
        # own spell reference (avoids a race where a later cast overwrites an
        # earlier one).
        _spell_queue: list[Any] = []

        def _cond_and_capture(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            """Check condition and enqueue the spell reference for the effect."""
            result = _condition(g, event)
            if result:
                _spell_queue.append(event.spell)
            return result

        def _casualty_effect(g: GameState) -> None:
            """Resolve the casualty trigger: offer sacrifice, copy spell."""
            if not _spell_queue:
                return
            spell = _spell_queue.pop(0)

            # Ask the controller if they want to pay casualty
            pay = controller.choose_yes_no(
                "Pay casualty 1? (Sacrifice a creature with power >= 1)"
            )
            if not pay:
                return

            # Find eligible creatures (power >= 1) controlled by the controller
            battlefield = g.get_battlefield(controller)
            eligible = [
                obj for obj in battlefield.get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "power", 0) >= 1
            ]

            if not eligible:
                return

            # Ask the controller to choose a creature to sacrifice
            chosen = controller.choose(
                eligible,
                "Choose a creature to sacrifice for casualty 1",
            )

            # Validate the chosen creature is in the eligible list
            if chosen is None or chosen not in eligible:
                return

            # Sacrifice: remove from battlefield, put in owner's graveyard
            battlefield.remove(chosen)
            owner = getattr(chosen, "owner", controller)
            if owner is None:
                owner = controller
            g.get_graveyard(owner).add(chosen)

            # Find the original spell's StackObject on the stack
            original_stack_obj = None
            for stack_obj in g.stack.objects():
                if stack_obj.source is spell:
                    original_stack_obj = stack_obj
                    break

            if original_stack_obj is None:
                return

            # Copy the spell and push onto the stack
            spell_copy = copy_spell(g, original_stack_obj, controller)

            # Ask if the controller wants to choose new targets for the copy
            controller.choose_yes_no("Choose new targets for the copy?")

            g.stack.push(spell_copy)

        trigger = TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_cond_and_capture,
            effect=_casualty_effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)
