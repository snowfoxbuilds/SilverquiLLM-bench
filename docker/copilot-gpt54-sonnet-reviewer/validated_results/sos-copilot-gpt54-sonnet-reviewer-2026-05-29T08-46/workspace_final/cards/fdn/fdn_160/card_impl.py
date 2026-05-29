"""Card implementation for An Offer You Can't Refuse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

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
    from engine.casting import counter_spell

    counter_spell(game, stack_obj)


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

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a noncreature spell on the stack."""
        from engine.types import CardType

        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            card_types = getattr(source, "card_types", set())
            # Must be a spell (has spell card types) and not a creature
            is_spell = bool(card_types - {CardType.LAND})
            if is_spell and CardType.CREATURE not in card_types:
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target noncreature spell on the stack."""
        from engine.types import CardType

        def _filter(obj: Any) -> bool:
            if obj is self:
                return False
            source = getattr(obj, "source", obj)
            card_types = getattr(source, "card_types", set())
            # Must be a spell (has spell card types, not just a land) and noncreature
            is_spell = bool(card_types - {CardType.LAND})
            return is_spell and CardType.CREATURE not in card_types

        return [
            TargetRequirement(
                filter_fn=_filter,
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
            for _ in range(2):
                from engine.card import CardImpl
                treasure = CardImpl(
                    name="Treasure",
                    mana_cost=ManaCost(generic=0),
                    rules_text="{T}, Sacrifice this token: Add one mana of any color.",
                )
                treasure.card_types = {CardType.ARTIFACT}
                treasure.subtypes = {"Treasure"}
                treasure.is_token = True
                create_token(game, spell_controller, treasure)
