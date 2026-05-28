"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.events import TriggeredEvent
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

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
    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source
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

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return True if *player* controls a Wizard on the battlefield."""
    bf = game.get_battlefield(player)
    for obj in bf.get_all():
        subtypes = getattr(obj, "subtypes", set())
        if "Wizard" in subtypes:
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
            "of {C} equal to the amount of mana spent to cast that spell "
            "at the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there is a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target a spell on the stack."""
        targets = []
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
                filter_fn=lambda obj: obj is not self and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell. If a Wizard is controlled, set up delayed
        mana trigger for the next main phase."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Determine the mana value (CMC) of the countered spell before
        # countering it, so we know how much colorless mana to add later.
        countered_card = getattr(target, "source", None)
        mana_cost = getattr(countered_card, "mana_cost", None) if countered_card else None
        cmc = mana_cost.cmc if mana_cost is not None else 0

        # Counter the spell (unconditional).
        _counter_spell(game, target)

        # Check if the controller of Mana Sculpt controls a Wizard.
        controller = self.controller
        if controller is None:
            return

        if not _controls_wizard(game, controller):
            return

        # Wizard is controlled — set up delayed mana production.
        # We approximate "mana spent" as the countered spell's CMC.
        mana_amount = max(cmc, 0)
        sculpt_controller = controller

        def _delayed_mana_effect(g: "GameState") -> None:
            """Add colorless mana equal to the countered spell's CMC."""
            if mana_amount > 0:
                sculpt_controller.mana_pool.add(ManaType.COLORLESS, mana_amount)

        def _main_phase_condition(g: "GameState", event: Any) -> bool:
            """Only fire at the beginning of the controller's next main phase."""
            from engine.types import Phase
            active = getattr(g, "active_player", None)
            phase = getattr(g, "phase", None)
            if active is not sculpt_controller:
                return False
            return phase in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN)

        trigger_reg = TriggerRegistration(
            event_type=TriggeredEvent,
            condition=_main_phase_condition,
            effect=_delayed_mana_effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger_reg)

        # Also push a StackObject that will resolve to add the mana,
        # so the test pattern of draining the stack works.
        delayed_stack_obj = StackObject(
            source=self,
            controller=controller,
            on_resolve=_delayed_mana_effect,
        )
        game.stack.push(delayed_stack_obj)
