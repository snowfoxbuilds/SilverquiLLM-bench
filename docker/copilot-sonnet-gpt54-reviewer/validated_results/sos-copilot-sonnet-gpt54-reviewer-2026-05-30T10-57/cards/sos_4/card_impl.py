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
        # Set externally during casting (count of distinct colors spent).
        self.colors_spent: int = 0

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: a player to draw, and any target to deal damage."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
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
        """Apply converge effects: draw X, deal X damage, gain X life."""
        from engine.game import deal_damage, draw_card

        x = self.colors_spent
        if x <= 0:
            return

        controller = self.controller
        targets = getattr(self, "chosen_targets", None) or []

        # chosen_targets[0] = target player who draws cards
        # chosen_targets[1] = any target that takes X damage
        draw_target = targets[0] if len(targets) > 0 else None
        damage_target = targets[1] if len(targets) > 1 else None

        # Target player draws X cards.
        if draw_target is not None:
            for _ in range(x):
                draw_card(game, draw_target)

        # Deal X damage to any target (player or creature) via engine helper.
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # Controller gains X life.
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
