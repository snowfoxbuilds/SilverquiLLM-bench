"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> Any:
    """Counter a spell — remove it from the stack and move the card to graveyard."""
    from engine.stack import StackObject
    from engine.types import Zone

    if not isinstance(stack_obj, StackObject):
        return None

    card = stack_obj.source
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


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U}."""

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
        """Cannot cast unless there is another spell on the stack."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target a spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell, then possibly schedule delayed mana."""
        target = _get_chosen_target(self)
        if target is None:
            return

        target_card = getattr(target, "source", None)
        mana_spent = getattr(target_card, "total_mana_spent", None)
        if mana_spent is None:
            mana_cost = getattr(target_card, "mana_cost", None)
            mana_spent = mana_cost.cmc if mana_cost is not None else 0

        countered_card = _counter_spell(game, target)
        if countered_card is None:
            return

        controller = self.controller
        if controller is None or not self._controls_wizard(game, controller):
            return

        def _add_mana(g: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, int(mana_spent))

        game.schedule_for_next_main_phase(controller, _add_mana)

    @staticmethod
    def _controls_wizard(game: "GameState", player: Any) -> bool:
        """Return True if *player* controls a Wizard creature."""
        battlefield = game.get_battlefield(player)
        for permanent in battlefield.get_all():
            if not isinstance(permanent, Creature):
                continue
            if CardType.CREATURE not in getattr(permanent, "card_types", set()):
                continue
            if "Wizard" in getattr(permanent, "subtypes", set()):
                return True
        return False
