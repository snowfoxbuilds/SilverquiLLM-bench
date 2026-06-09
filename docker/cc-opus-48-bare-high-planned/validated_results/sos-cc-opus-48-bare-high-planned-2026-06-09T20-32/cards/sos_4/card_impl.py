"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and not hasattr(obj, "card_types")


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage to
    any target, and you gain X life, where X is the number of colors of mana
    spent to cast this spell.

    SOS collector number 4.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """A target player and an 'any target' (player or creature)."""
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda o: _is_player(o) or _is_creature(o),
                description="any target (player or creature)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Converge: X = number of colors of mana spent to cast this spell."""
        from engine.game import deal_damage, draw_card

        colors_spent = getattr(self, "colors_spent", [])
        x = len(set(colors_spent))

        targets = getattr(self, "chosen_targets", [])
        target_player = targets[0] if len(targets) > 0 else None
        any_target = targets[1] if len(targets) > 1 else None

        if target_player is not None:
            for _ in range(x):
                draw_card(game, target_player)

        if any_target is not None and x > 0:
            deal_damage(game, self, any_target, x)

        if self.controller is not None and x > 0:
            self.controller.life += x
