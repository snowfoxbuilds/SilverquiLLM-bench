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
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: target player (draws), any target (damage)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") and hasattr(obj, "zones"),
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
        """X = number of colors spent; draw X, deal X damage, gain X life."""
        from engine.game import deal_damage, draw_card

        colors_spent = getattr(self, "colors_spent", [])
        x = len(set(colors_spent))

        targets = getattr(self, "chosen_targets", [])
        target_player = targets[0] if len(targets) > 0 else None
        damage_target = targets[1] if len(targets) > 1 else None
        controller = self.controller

        if x == 0:
            # X=0: draws/deals/gains 0 — nothing to do
            return

        # Target player draws X cards
        if target_player is not None and hasattr(target_player, "zones"):
            for _ in range(x):
                draw_card(game, target_player)

        # Deal X damage to any target
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # Controller gains X life
        if controller is not None:
            controller.life += x
