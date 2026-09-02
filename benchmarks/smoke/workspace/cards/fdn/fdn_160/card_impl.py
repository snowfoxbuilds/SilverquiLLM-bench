"""Card implementation for An Offer You Can't Refuse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
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


class AnOfferYouCantRefuse(Instant):
    """An Offer You Can't Refuse — {U} — Instant.

    Counter target noncreature spell. Its controller creates two Treasure
    tokens.

    FDN collector number 160.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "An Offer You Can't Refuse")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target noncreature spell. Its controller creates two "
            "Treasure tokens.",
        )
        super().__init__(**kwargs)

    def _is_noncreature_spell(self, stack_obj: Any) -> bool:
        """True iff *stack_obj* is a noncreature-spell OCCURRENCE (not this cast).

        ``StackObject.is_spell`` is the discriminator: a triggered/activated
        ability may share its source card with a pending spell but is not
        itself a spell, and must never be offered as a "target noncreature
        spell".
        """
        from engine.types import CardType

        if not getattr(stack_obj, "is_spell", False):
            return False
        source = getattr(stack_obj, "source", None)
        if source is self:
            return False
        return CardType.CREATURE not in getattr(source, "card_types", set())

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a noncreature spell on the stack."""
        return any(self._is_noncreature_spell(so) for so in game.stack.objects())

    def get_targets(self, game: "GameState") -> list:
        """Target noncreature spell on the stack — an exact StackObject occurrence."""
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=self._is_noncreature_spell,
                description="target noncreature spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target noncreature spell, give its controller two Treasure tokens."""
        from engine.game import create_token
        from engine.card import Creature

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Get the controller of the countered spell before countering
        spell_controller = getattr(target, "controller", None)

        _counter_spell(game, target)

        # Create two Treasure tokens for the spell's controller
        if spell_controller is not None:
            from cards.fdn.tokens import make_treasure_token
            create_token(
                game, spell_controller, factory=make_treasure_token, count=2
            )
