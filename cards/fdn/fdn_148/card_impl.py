"""Card implementation for Stroke of Midnight."""

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
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)
def _create_human_token(game: GameState, player: Any) -> Any:
    """Create a 1/1 white Human creature token on *player*'s battlefield."""
    from engine.card import Creature
    from engine.game import create_token

    token = Creature(
        name="Human Token",
        mana_cost=ManaCost(),
        rules_text="",
        base_power=1,
        base_toughness=1,
    )
    token.card_types = {CardType.CREATURE}
    create_token(game, player, token)
    return token

class StrokeOfMidnight(Instant):
    """Stroke of Midnight — {2}{W} — Destroy target nonland permanent.
    Its controller creates a 1/1 white Human creature token.

    FDN collector number 148.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stroke of Midnight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target nonland permanent. Its controller creates a "
            "1/1 white Human creature token.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target nonland permanent on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.LAND not in card_types:
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.LAND not in getattr(obj, "card_types", set()),
                description="target nonland permanent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target; its controller gets a 1/1 Human token."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return

        target_controller = getattr(target, "controller", None)
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                card_types = getattr(target, "card_types", set())
                if CardType.LAND not in card_types:
                    destroy(game, target)
                    # Create a 1/1 white Human token for the controller
                    if target_controller is not None:
                        _create_human_token(game, target_controller)
                    return
