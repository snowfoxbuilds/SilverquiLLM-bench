"""Card implementation for Mana Sculpt (SOS 57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source

    # Remove from the stack
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    # Remove from the player's stack zone
    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    # Move to owner's graveyard
    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


def _controls_wizard(player: Any) -> bool:
    """Return True if *player* controls at least one Wizard on their battlefield."""
    try:
        bf = player.zones[Zone.BATTLEFIELD]
    except (KeyError, TypeError, AttributeError):
        return False
    for obj in bf.get_all():
        subtypes = getattr(obj, "subtypes", set())
        if "Wizard" in subtypes:
            controller = getattr(obj, "controller", None)
            # Only count if actually controlled by this player
            if controller is None or controller is player:
                return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount "
            "of {C} equal to the amount of mana spent to cast that spell at "
            "the beginning of your next main phase.",
        )
        super().__init__(**kwargs)
        # Tracks the amount of colorless mana to add at next main phase.
        self.pending_mana_amount: int | None = None

    def can_cast(self, game: "GameState") -> bool:
        """Can only cast if there is a valid target spell on the stack."""
        for stack_obj in game.stack.objects():
            source = getattr(stack_obj, "source", None)
            if source is self:
                continue
            # Any spell on the stack is a valid target
            card_types = getattr(source, "card_types", set())
            is_spell = bool(card_types - {CardType.LAND})
            if is_spell:
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return a TargetRequirement for any spell on the stack."""
        source_self = self

        def _filter(obj: Any) -> bool:
            # Reject if this is ManaSculpt itself
            src = getattr(obj, "source", obj)
            if src is source_self:
                return False
            # Accept any StackObject whose source is a spell
            from engine.stack import StackObject
            if not isinstance(obj, StackObject):
                return False
            card_types = getattr(src, "card_types", set())
            is_spell = bool(card_types - {CardType.LAND})
            return is_spell

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell. If you control a Wizard, schedule mana bonus."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Determine the amount of mana spent to cast the countered spell.
        # Prefer a 'mana_spent' attribute on the StackObject (which would capture
        # the actual amount paid including any X value); fall back to the card's
        # mana value (CMC) which treats X as 0 and is therefore only correct for
        # spells without {X} in their cost.
        mana_spent = getattr(target, "mana_spent", None)
        if mana_spent is not None:
            cmc = int(mana_spent)
        else:
            source_card = getattr(target, "source", None)
            mana_cost = getattr(source_card, "mana_cost", None) if source_card is not None else None
            cmc = mana_cost.cmc if mana_cost is not None else 0

        # Counter the spell
        _counter_spell(game, target)

        # Check if controller controls a Wizard
        controller = self.controller
        if controller is None:
            return

        if not _controls_wizard(controller):
            return

        # Schedule the mana bonus at the beginning of next main phase
        self.pending_mana_amount = cmc
        spell_impl = self

        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            """Only fire for the controller's main phase."""
            return event.player is controller

        def _effect(game: "GameState") -> None:
            """Add the pending colorless mana to the controller's mana pool."""
            amount = getattr(spell_impl, "pending_mana_amount", 0) or 0
            if amount > 0:
                controller.mana_pool.add(ManaType.COLORLESS, amount)
            # Unregister this trigger so it only fires once
            game.trigger_manager.unregister(spell_impl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=spell_impl,
                controller=controller,
            )
        )
