"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon 4/4.

    Flying, Vigilance.
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1 or greater.
    When you do, copy the spell and you may choose new targets for the copy.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "supertypes",
            {Supertype.LEGENDARY},
        )
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Flying, Vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power 1 "
            "or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    def is_casualty_eligible(self, spell: Any) -> bool:
        """Return True if *spell* is an instant or sorcery (eligible for casualty 1)."""
        card_types = getattr(spell, "card_types", set())
        return CardType.INSTANT in card_types or CardType.SORCERY in card_types

    def register_triggers(self, game: "GameState") -> None:
        """Register the casualty 1 trigger on SpellCastTriggeredEvent."""

        silverquill = self

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            """Fire only for instants/sorceries cast by this card's controller."""
            if event.controller is not silverquill.controller:
                return False
            result = silverquill.is_casualty_eligible(event.spell)
            if result:
                # Populate the event on game so _effect can retrieve the spell
                # during real gameplay (the engine does not set this attribute
                # automatically; we do it here in the condition so both test
                # code that manually sets game._last_spell_cast_event and real
                # gameplay via the condition path will work correctly).
                game._last_spell_cast_event = event
            return result

        def _effect(game: "GameState") -> None:
            """Casualty 1 effect: optionally sacrifice a creature to copy the spell."""
            from engine.events import SacrificeReplacementEvent
            from engine.stack import StackObject, copy_spell
            from engine.zones import move_to_zone

            event: SpellCastTriggeredEvent | None = getattr(
                game, "_last_spell_cast_event", None
            )
            if event is None:
                return

            spell = event.spell
            controller = silverquill.controller

            # Issue 3 fix: verify the original spell is still on the stack
            # BEFORE paying any costs.  If it has been countered or removed,
            # there is nothing to copy and the sacrifice should not happen.
            original_stack_obj: StackObject | None = None
            for obj in game.stack._items:
                if obj.source is spell:
                    original_stack_obj = obj
                    break

            if original_stack_obj is None:
                return

            # Find eligible sacrifice targets: creatures on controller's
            # battlefield with power >= 1.
            battlefield = game.get_battlefield(controller)
            eligible = [
                obj
                for obj in battlefield.get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "power", 0) >= 1
            ]

            if not eligible:
                return

            # Ask the controller whether they want to sacrifice.
            wants_sacrifice = controller.choose_yes_no(
                "Casualty 1: sacrifice a creature with power 1 or greater to copy the spell?"
            )
            if not wants_sacrifice:
                return

            # Ask which creature to sacrifice.
            sacrifice_target = controller.choose_card(
                eligible, "Choose a creature to sacrifice for casualty 1"
            )

            # Issue 2 fix: use move_to_zone so leave-battlefield and dies
            # triggers fire and replacement effects are consulted.
            move_to_zone(
                game,
                sacrifice_target,
                Zone.BATTLEFIELD,
                Zone.GRAVEYARD,
                replacement_event=SacrificeReplacementEvent(
                    permanent=sacrifice_target,
                    controller=getattr(sacrifice_target, "controller", controller),
                    owner=getattr(sacrifice_target, "owner", controller),
                ),
            )

            # Copy the spell and push onto the stack.
            # Players may choose new targets for the copy in a full game loop;
            # target selection is deferred to the resolution phase.
            copy_obj = copy_spell(game, original_stack_obj, controller)
            game.stack.push(copy_obj)

        trigger = TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=self.controller,
        )
        game.trigger_manager.register(trigger)
