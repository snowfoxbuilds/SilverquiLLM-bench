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
    """Counter a spell via the engine's shared stack-departure primitive.

    :func:`engine.stack.move_spell_off_stack` removes exactly *stack_obj* and
    puts an ordinary spell in its owner's graveyard — or exiles it when the
    cast stamped a departure replacement (a flashback cast, rule 702.34a).
    If *stack_obj* already left the stack, nothing happens (fizzle).
    """
    from engine.stack import StackObject, move_spell_off_stack

    if not isinstance(stack_obj, StackObject):
        return
    move_spell_off_stack(game, stack_obj)

class EssenceScatter(Instant):
    """Essence Scatter — {1}{U} — Counter target creature spell.

    FDN collector number 153.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Essence Scatter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("rules_text", "Counter target creature spell.")
        super().__init__(**kwargs)

    def _is_creature_spell(self, stack_obj: Any) -> bool:
        """True iff *stack_obj* is a creature-spell OCCURRENCE (not this cast).

        ``StackObject.is_spell`` is the discriminator: an ability on the stack
        may share its source card with a creature spell (or be sourced by a
        battlefield creature) but is not itself a creature spell.
        """
        if not getattr(stack_obj, "is_spell", False):
            return False
        source = getattr(stack_obj, "source", None)
        if source is self:
            return False
        return CardType.CREATURE in getattr(source, "card_types", set())

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast unless a creature spell is on the stack."""
        return any(self._is_creature_spell(so) for so in game.stack.objects())

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature spell on the stack — an exact StackObject occurrence."""
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=self._is_creature_spell,
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
