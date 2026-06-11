"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

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

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: target player (draw), any target (damage)."""
        from engine.types import TargetRequirement

        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="target player",
                zone=Zone.BATTLEFIELD,  # placeholder zone
            ),
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: draw X, deal X damage, gain X life."""
        from engine.game import draw_card, deal_damage

        colors_spent = getattr(self, "colors_spent", None)
        if colors_spent is None:
            x = 0
        elif isinstance(colors_spent, (list, tuple)):
            x = len(set(colors_spent))
        else:
            x = int(colors_spent)

        if x == 0:
            return

        controller = self.controller or self.owner
        if controller is None:
            return

        # Get targets: [draw_target_player, damage_target]
        chosen = getattr(self, "chosen_targets", None)
        if not chosen or len(chosen) < 2:
            return

        draw_target = chosen[0]
        damage_target = chosen[1]

        # Draw X cards for target player
        for _ in range(x):
            draw_card(game, draw_target)

        # Deal X damage to damage target
        if hasattr(damage_target, "damage_marked"):
            # It's a creature
            damage_target.damage_marked += x
        elif hasattr(damage_target, "life"):
            # It's a player
            damage_target.life -= x

        # Controller gains X life
        controller.life += x
