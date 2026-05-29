"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from engine.stack import StackObject


def _get_chosen_target(card: Any) -> Any:
    """Return the first chosen target, if any."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _is_spell_stack_object(obj: Any) -> bool:
    """Return True if *obj* is a spell on the stack."""
    return getattr(obj, "is_spell", True)


def _counter_spell(game: GameState, stack_obj: Any) -> Any | None:
    """Counter *stack_obj* and return the countered spell card."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return None

    card = stack_obj.source

    stack_items = game.stack._items  # noqa: SLF001
    for index, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(index)
            break
    else:
        return None

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    spell_was_card = False
    for player in game.players:
        stack_zone = player.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)
            spell_was_card = True
            break

    if spell_was_card and owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)

    return card


def _controls_wizard(game: GameState, player: Player | None) -> bool:
    """Return True if *player* controls a Wizard."""
    if player is None:
        return False
    for permanent in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


def _mana_spent_for_spell(card: Any) -> int:
    """Return the tracked mana spent to cast *card*, if known."""
    tracked = getattr(card, "mana_spent_to_cast", None)
    if isinstance(tracked, int):
        return tracked
    return 0


class ManaSculpt(Instant):
    """Mana Sculpt — counter a spell, then maybe bank colorless mana."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} "
            "equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Mana Sculpt requires another spell on the stack."""
        for stack_obj in game.stack.objects():
            if _is_spell_stack_object(stack_obj):
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=_is_spell_stack_object,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Counter the target spell and, if appropriate, delay colorless mana."""
        target = _get_chosen_target(self)
        if target is None:
            return

        target_card = getattr(target, "source", None)
        mana_amount = _mana_spent_for_spell(target_card) if target_card is not None else 0
        should_add_mana = _controls_wizard(game, self.controller)

        countered_card = _counter_spell(game, target)
        if countered_card is None or not should_add_mana or mana_amount <= 0:
            return

        controller = self.controller
        if controller is None:
            return

        def _add_mana(g: GameState) -> None:
            controller.mana_pool.add(ManaType.COLORLESS, mana_amount)

        game.schedule_beginning_of_next_main_phase(controller, _add_mana)
