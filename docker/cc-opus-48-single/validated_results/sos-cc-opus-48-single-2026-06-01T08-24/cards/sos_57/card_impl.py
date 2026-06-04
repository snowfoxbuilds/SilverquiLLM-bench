"""Card implementation for Mana Sculpt (SOS 57).

    "Counter target spell. If you control a Wizard, add an amount of {C} equal
    to the amount of mana spent to cast that spell at the beginning of your
    next main phase."

The counter half is fully implemented and tested.  The delayed Wizard {C}
bonus is built on top of two ADDITIVE engine capabilities:

* ``engine.events.BeginningOfMainPhaseTriggeredEvent`` — fired from
  ``GameState.advance_phase`` whenever a main phase begins.
* ``card.mana_spent`` — total mana paid to cast a spell, recorded by
  ``engine.casting.cast_spell``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# Card types that count as a "spell" while on the stack.
_SPELL_TYPES = {
    CardType.INSTANT,
    CardType.SORCERY,
    CardType.CREATURE,
    CardType.ARTIFACT,
    CardType.ENCHANTMENT,
    CardType.PLANESWALKER,
}


def _is_spell(obj: Any) -> bool:
    """Return ``True`` if *obj* (a card or stack object) is a spell.

    Accepts either the card directly or a ``StackObject`` wrapping a card.
    """
    source = getattr(obj, "source", obj)
    card_types = getattr(source, "card_types", set())
    return bool(card_types & _SPELL_TYPES)


def _find_stack_object(game: GameState, card: Any) -> Any:
    """Return the StackObject whose ``source`` is *card*, or ``None``."""
    from engine.stack import StackObject

    if isinstance(card, StackObject):
        return card
    for stack_obj in game.stack.objects():
        if stack_obj.source is card:
            return stack_obj
    return None


def _counter_spell(game: GameState, stack_obj: Any) -> Any:
    """Counter the spell represented by *stack_obj*.

    Removes the StackObject from the stack, moves its source card from the
    controller's STACK zone to its owner's graveyard, and never runs the
    spell's ``on_resolve``.  Returns the countered card (or ``None``).
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return None

    card = stack_obj.source

    # Remove the StackObject from the stack; fizzle if it is no longer there.
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break
    if not found:
        return None

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)

    return card


def _controls_wizard(game: GameState, player: Any) -> bool:
    """Return ``True`` if *player* controls a creature with the Wizard subtype."""
    if player is None:
        return False
    for perm in game.get_battlefield(player).get_all():
        subtypes = getattr(perm, "subtypes", set())
        if "Wizard" in subtypes:
            return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Counter target spell with a Wizard {C} bonus."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: GameState) -> list[Any]:
        """Advertise a single "target spell" requirement in the STACK zone."""
        # While this spell is itself on the stack being cast, don't advertise
        # a self-target requirement (KEY_DECISIONS sos_1 convention).
        return [
            TargetRequirement(
                filter_fn=_is_spell,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Counter the chosen spell; queue the Wizard {C} bonus if applicable."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        stack_obj = _find_stack_object(game, target)
        if stack_obj is None:
            return

        # Record the mana spent on the countered spell BEFORE it leaves the
        # stack, for the delayed {C} bonus.
        countered_card = stack_obj.source
        mana_spent = int(getattr(countered_card, "mana_spent", 0) or 0)

        countered = _counter_spell(game, stack_obj)
        if countered is None:
            return

        # --- Wizard {C} bonus (delayed to your next main phase) ---
        controller = self.controller
        if _controls_wizard(game, controller) and mana_spent > 0:
            self._register_mana_bonus(game, controller, mana_spent)

    def _register_mana_bonus(
        self, game: GameState, controller: Any, amount: int
    ) -> None:
        """Register a one-shot delayed trigger that adds {C} at the next main phase.

        Uses the additive ``BeginningOfMainPhaseTriggeredEvent`` engine hook.
        """
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        fired = {"done": False}

        def _condition(g: GameState, event: Any) -> bool:
            if fired["done"]:
                return False
            return getattr(event, "player", None) is controller

        def _effect(g: GameState) -> None:
            if fired["done"]:
                return
            fired["done"] = True
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            # One-shot: remove this delayed trigger after it resolves.
            g.trigger_manager.unregister(self)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
