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

    SOS collector number 4.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost(generic=6))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Two targets: a player, and any target (player or creature)."""

        def _any_target(obj: Any) -> bool:
            if hasattr(obj, "life"):
                return True
            return CardType.CREATURE in getattr(obj, "card_types", set())

        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=_any_target,
                description="any target (player or creature)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Apply Converge effects based on number of colors spent."""
        from engine.game import deal_damage, draw_card

        colors_spent = getattr(self, "colors_spent", [])
        x = len(set(colors_spent))

        targets = getattr(self, "chosen_targets", [])
        target_player = targets[0] if len(targets) > 0 else None
        any_target = targets[1] if len(targets) > 1 else None

        controller = self.controller

        # Draw X cards for target player
        if target_player is not None and x > 0:
            for _ in range(x):
                draw_card(game, target_player)

        # Deal X damage to any target
        if any_target is not None and x > 0:
            deal_damage(game, self, any_target, x)

        # You gain X life
        if controller is not None and x > 0:
            controller.life += x
