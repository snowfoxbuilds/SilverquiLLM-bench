"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> bool:
    """Counter a spell — remove it from the stack and move the card to
    its owner's graveyard.

    Returns ``True`` if a spell was actually countered (the stack object
    was found on the stack), ``False`` otherwise (fizzle / illegal target).
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return False

    card = stack_obj.source

    # Check if the stack object is actually on the stack; if not, fizzle.
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return False

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)

    return True


def _controls_a_wizard(game: "GameState", player: Any) -> bool:
    """True if *player* controls a Wizard on the battlefield."""
    if player is None:
        return False
    battlefield = player.zones[Zone.BATTLEFIELD]
    for obj in battlefield.get_all():
        if "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


def _mana_spent_to_cast(card: Any) -> int:
    """Amount of mana spent to cast *card*.

    Uses the engine-recorded ``mana_spent`` (set in ``engine.casting`` after
    payment) when present, falling back to the card's mana value
    (``mana_cost.cmc``) otherwise — e.g. when a test places a spell directly
    on the stack without paying.  For a normally-cast, no-X / non-reduced
    spell the two are equal.
    """
    recorded = getattr(card, "mana_spent", None)
    if isinstance(recorded, int):
        return recorded
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is not None:
        return mana_cost.cmc
    return 0


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
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's another spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            # "Counter target spell" — any spell, not just creature spells.
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target any spell on the stack (other than Mana Sculpt itself)."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: getattr(obj, "source", obj) is not self
                and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell; if you control a Wizard, set up the
        deferred {C} for your next main phase."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        countered_card = getattr(target, "source", None)
        if not _counter_spell(game, target):
            # No legal target was countered — the spell fizzles; nothing
            # else happens (no deferred mana).
            return

        controller = self.controller
        if controller is None:
            return

        # "If you control a Wizard" — evaluated as the counter resolves.
        if not _controls_a_wizard(game, controller):
            return

        amount = _mana_spent_to_cast(countered_card)

        def _add_deferred_mana(g: "GameState") -> None:
            if amount > 0:
                controller.mana_pool.add(ManaType.COLORLESS, amount)

        # Delayed one-shot trigger: at the beginning of the controller's
        # next main phase, add {C} equal to the mana spent, then remove
        # itself (one-shot semantics handled by the trigger manager).
        game.trigger_manager.register_delayed(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            effect=_add_deferred_mana,
            source=self,
            controller=controller,
            condition=lambda g, event: getattr(event, "player", None) is controller,
        )
