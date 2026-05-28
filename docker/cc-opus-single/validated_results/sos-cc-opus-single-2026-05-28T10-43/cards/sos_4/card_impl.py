"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals "
            "X damage to any target, and you gain X life, where X is the "
            "number of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        self.colors_spent: list[Any] = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return two target requirements: a target player, and any target."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") and not hasattr(obj, "card_types"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "life")
                    or CardType.CREATURE in getattr(obj, "card_types", set())
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: draw X, deal X damage, gain X life."""
        from engine.game import deal_damage, draw_card

        # Determine X = number of distinct colors spent
        colors = getattr(self, "colors_spent", [])
        x = len(set(colors))

        if x == 0:
            return

        # Get targets
        chosen = getattr(self, "chosen_targets", None)
        if not chosen or len(chosen) < 2:
            return

        draw_target = chosen[0]   # target player (draws X cards)
        damage_target = chosen[1]  # any target (takes X damage)
        controller = self.controller

        # 1. Target player draws X cards
        if hasattr(draw_target, "life"):
            for _ in range(x):
                draw_card(game, draw_target)

        # 2. Deal X damage to any target
        deal_damage(game, self, damage_target, x)

        # 3. Controller gains X life
        if controller is not None:
            controller.life += x
