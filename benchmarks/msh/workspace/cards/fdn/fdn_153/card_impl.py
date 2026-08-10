"""Card implementation for Essence Scatter."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None
def _counter_spell(game: GameState, stack_obj: Any) -> None:
    """Counter a spell — remove it from the stack and move the card to
    its owner's graveyard.
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

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

class EssenceScatter(Instant):
    """Essence Scatter — {1}{U} — Counter target creature spell.

    FDN collector number 153.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Essence Scatter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("rules_text", "Counter target creature spell.")
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast unless a creature spell is on the stack."""
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            card_types = getattr(source, "card_types", set())
            if CardType.CREATURE in card_types:
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature spell on the stack."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            card_types = getattr(source, "card_types", set())
            if CardType.CREATURE in card_types:
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(getattr(obj, "source", obj), "card_types", set()),
                description="target creature spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Counter the target creature spell."""
        target = _get_chosen_target(self, game)
        if target is None:
            return
        _counter_spell(game, target)
