"""Card implementation for Mana Sculpt."""

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
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard."""
    from engine.stack import StackObject

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
    """Return True if player controls a Wizard on the battlefield."""
    from engine.card import Creature

    bf = game.get_battlefield(player)
    return any(
        "Wizard" in getattr(c, "subtypes", set())
        for c in bf.get_all()
        if isinstance(c, Creature)
    )


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
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
        # Colorless mana to grant at start of next main phase (set on resolve).
        self.mana_to_add: int = 0

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a spell on the stack to counter."""
        from engine.stack import StackObject

        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj, _self=self: (
                    hasattr(obj, "source")
                    and obj.source is not _self
                    and getattr(obj, "is_spell", True)
                ),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell. If controlling a Wizard, grant {C} next main phase."""
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Determine CMC of the countered spell before countering it
        countered_card = getattr(target, "source", None)
        cmc = 0
        if countered_card is not None:
            mana_cost = getattr(countered_card, "mana_cost", None)
            if mana_cost is not None:
                cmc = mana_cost.cmc

        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        if cmc > 0 and _controls_wizard(game, controller):
            # Schedule mana grant at beginning of controller's next main phase.
            # We use a one-shot upkeep trigger as a proxy (fires start of next turn).
            mana_amount = cmc
            triggered = False

            class _Sentinel:
                pass

            src = _Sentinel()

            def condition2(g: "GameState", event: Any) -> bool:
                nonlocal triggered
                if triggered:
                    return False
                return g.active_player is controller

            def effect2(g: "GameState") -> None:
                nonlocal triggered
                triggered = True
                controller.mana_pool.add(ManaType.COLORLESS, mana_amount)
                g.trigger_manager.unregister(src)

            game.trigger_manager.register(
                TriggerRegistration(
                    event_type=BeginningOfUpkeepTriggeredEvent,
                    condition=condition2,
                    effect=effect2,
                    source=src,
                    controller=controller,
                )
            )
