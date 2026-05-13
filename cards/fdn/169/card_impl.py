"""Card implementation for Bake into a Pie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Artifact, Instant
from engine.game import create_token, destroy
from engine.types import (
    CardType,
    ManaCost,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState




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

def _create_food_token(game: GameState, player: Any) -> Any:
    """Create a Food artifact token on *player*'s battlefield."""
    from engine.card import Artifact
    from engine.game import create_token

    token = Artifact(
        name="Food Token",
        mana_cost=ManaCost(),
        rules_text='{2}, {T}, Sacrifice this token: You gain 3 life.',
    )
    token.card_types = {CardType.ARTIFACT}
    create_token(game, player, token)
    return token
class BakeIntoAPie(Instant):
    """Bake into a Pie — {2}{B}{B} — Destroy target creature.
    Create a Food token.

    FDN collector number 169.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bake into a Pie")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            'Destroy target creature. Create a Food token. (It\'s an '
            'artifact with "{2}, {T}, Sacrifice this token: You gain '
            '3 life.")',
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target creature; create a Food token."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return
        # Verify target is still legal; if not, spell fizzles entirely
        target_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    target_valid = True
                    break
        if not target_valid:
            return
        destroy(game, target)
        # Create a Food token for the controller
        controller = self.controller
        if controller is not None:
            _create_food_token(game, controller)
