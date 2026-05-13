"""Card implementation for Incinerating Blast."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.game import deal_damage, discard
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
class IncineratingBlast(Sorcery):
    """Incinerating Blast — {4}{R} — Deal 6 damage to target creature.

    The optional loot effect (discard/draw) is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Incinerating Blast")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Incinerating Blast deals 6 damage to target creature.\n"
            "You may discard a card. If you do, draw a card.",
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

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast if no creature on the battlefield."""
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    return True
        return False

    def on_resolve(self, game: GameState) -> None:
        """Deal 6 damage to the chosen creature."""
        from engine.game import deal_damage

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a creature on the battlefield.
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    deal_damage(game, self, target, 6)
                    return
