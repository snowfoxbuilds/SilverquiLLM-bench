"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _is_spell_stack_object(stack_obj: Any) -> bool:
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return False

    if getattr(stack_obj, "is_spell", False):
        return True

    source = getattr(stack_obj, "source", None)
    controller = getattr(stack_obj, "controller", None)
    if source is None or controller is None:
        return False

    return controller.zones[Zone.STACK].contains(source)


def _counter_spell(game: "GameState", stack_obj: Any) -> bool:
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return False

    if not _is_spell_stack_object(stack_obj):
        return False

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
    for index, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(index)
            break
    else:
        return False

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)

    return True


def _controls_wizard(game: "GameState", player: Any) -> bool:
    if player is None:
        return False
    for permanent in game.get_battlefield(player).get_all():
        if CardType.CREATURE not in getattr(permanent, "card_types", set()):
            continue
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — counter a spell and maybe rebate its spent mana later."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} "
            "equal to the amount of mana spent to cast that spell at the beginning "
            "of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if _is_spell_stack_object(stack_obj):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        from engine.stack import StackObject

        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=_is_spell_stack_object,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        target = _get_chosen_target(self)
        if target is None:
            return

        mana_spent = int(
            getattr(
                target,
                "total_mana_spent",
                getattr(getattr(target, "source", None), "total_mana_spent", 0),
            )
        )
        if not _counter_spell(game, target):
            return

        controller = self.controller
        if not _controls_wizard(game, controller):
            return
        self._register_next_main_phase_trigger(game, controller, mana_spent)

    def _register_next_main_phase_trigger(
        self,
        game: "GameState",
        controller: Any,
        mana_spent: int,
    ) -> None:
        delayed_source = object()

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return event.player is controller

        def _stack_factory(
            game: "GameState",
            event: BeginningOfMainPhaseTriggeredEvent,
            trigger: TriggerRegistration,
        ) -> Any:
            from engine.stack import StackObject

            game.trigger_manager.unregister(delayed_source)
            return StackObject(
                source=self,
                controller=controller,
                on_resolve=lambda g: controller.mana_pool.add(ManaType.COLORLESS, mana_spent),
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=lambda _game: None,
                stack_factory=_stack_factory,
                source=delayed_source,
                controller=controller,
            )
        )
