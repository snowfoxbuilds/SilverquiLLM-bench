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
    """Silverquill, the Disputant -- {2}{W}{B} -- 4/4 Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1
    or greater. When you do, copy the spell and you may choose new
    targets for the copy.)
    """

    # Casualty threshold: sacrifice a creature with power >= casualty_n
    casualty_n: int = 1

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword(0))
        kwargs["keywords"] = kwargs["keywords"] | Keyword.FLYING | Keyword.VIGILANCE
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        super().__init__(**kwargs)

    def can_pay_casualty(self, game: GameState, creature: Any) -> bool:
        """Check whether *creature* is a valid sacrifice for casualty 1.

        A creature is valid if its power is >= self.casualty_n (which is 1).
        """
        power = getattr(creature, "power", getattr(creature, "base_power", 0))
        return power >= self.casualty_n

    def register_triggers(self, game: GameState) -> None:
        """Register the casualty-granting trigger.

        Watches for SpellCastTriggeredEvent. When the controller casts an
        instant or sorcery, if casualty was paid (the spell has
        ``_casualty_paid = True`` and ``_casualty_sacrificed`` set), the
        sacrificed creature is moved to the graveyard and a copy of the
        spell is placed on the stack.
        """
        controller = self.controller
        silverquill = self

        # Shared queue between condition and effect closures.
        # When the condition matches, it appends the spell reference;
        # when the effect resolves, it pops the reference.  This ensures
        # the effect always operates on the exact spell that triggered it,
        # even when multiple instants/sorceries are on the stack.
        _pending_spells: list[Any] = []

        def _casualty_condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            """Match only instants/sorceries cast by the controller."""
            # Must be cast by the controller of Silverquill
            if event.controller is not controller:
                return False
            # Must be an instant or sorcery
            spell = event.spell
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Capture the spell reference for the effect closure
            _pending_spells.append(spell)
            return True

        def _casualty_effect(game: GameState) -> None:
            """If casualty was paid, sacrifice the creature and copy the spell."""
            # Retrieve the specific spell that triggered this effect
            if not _pending_spells:
                return
            spell = _pending_spells.pop(0)

            # Check if casualty was actually paid for this spell
            if not getattr(spell, "_casualty_paid", False):
                return

            # Sacrifice the creature (move to graveyard)
            sacrificed = getattr(spell, "_casualty_sacrificed", None)
            if sacrificed is not None:
                bf = game.get_battlefield(controller)
                if bf.contains(sacrificed):
                    bf.remove(sacrificed)
                    gy = game.get_graveyard(controller)
                    gy.add(sacrificed)

            # Find the stack object for this specific spell
            original_stack_obj = None
            for stack_obj in game.stack.objects():
                if stack_obj.source is spell:
                    original_stack_obj = stack_obj
                    break

            if original_stack_obj is None:
                return

            # Copy the spell onto the stack
            copy_obj = copy_spell(game, original_stack_obj, controller)
            game.stack.push(copy_obj)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_casualty_condition,
            effect=_casualty_effect,
            source=silverquill,
            controller=controller,
        ))
