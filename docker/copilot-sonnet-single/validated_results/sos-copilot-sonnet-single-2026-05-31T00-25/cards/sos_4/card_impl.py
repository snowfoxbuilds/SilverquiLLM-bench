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
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Number of distinct colors spent to cast; set externally (converge).
        self.converge_colors: int = 0

    def get_targets(self, game: "GameState") -> list:
        """Two targets: a player (draw X), any target (X damage)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player (draws X cards)",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") or hasattr(obj, "damage_marked"),
                description="any target (deals X damage)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Draw X for target player, deal X damage to any target, gain X life."""
        from engine.game import deal_damage, draw_card

        x = self.converge_colors
        if x <= 0:
            return

        targets = getattr(self, "chosen_targets", [])
        draw_target = targets[0] if len(targets) > 0 else None
        damage_target = targets[1] if len(targets) > 1 else None

        controller = self.controller
        if controller is None:
            return

        # Draw X cards for target player
        if draw_target is not None and hasattr(draw_target, "zones"):
            for _ in range(x):
                draw_card(game, draw_target)

        # Deal X damage to any target
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # You gain X life
        controller.life += x
