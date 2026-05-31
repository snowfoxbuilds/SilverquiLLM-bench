"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Color, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — Converge sorcery."""

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

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return the spell's target player and damage target requirements."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") and CardType.CREATURE not in getattr(obj, "card_types", set()),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") or CardType.CREATURE in getattr(obj, "card_types", set()),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Draw X, deal X damage, and gain X life where X is converge count."""
        from engine.game import deal_damage, draw_card

        chosen = getattr(self, "chosen_targets", []) or []
        draw_target = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None
        controller = self.controller
        if controller is None:
            return

        x = self._converge_value()

        if draw_target is not None:
            for _ in range(x):
                draw_card(game, draw_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        if x > 0:
            controller.life += x

    def _converge_value(self) -> int:
        """Return the number of distinct colors of mana spent to cast this spell."""
        colors_spent = getattr(self, "colors_spent", []) or []
        return len({color for color in colors_spent if isinstance(color, Color)})
