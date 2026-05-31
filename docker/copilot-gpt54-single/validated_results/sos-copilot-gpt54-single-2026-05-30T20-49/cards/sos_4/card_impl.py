"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — Converge sorcery."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X damage "
            "to any target, and you gain X life, where X is the number of colors "
            "of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target player, then any target."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") and not hasattr(obj, "card_types"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: (
                    (hasattr(obj, "life") and not hasattr(obj, "card_types"))
                    or CardType.CREATURE in getattr(obj, "card_types", set())
                    or CardType.PLANESWALKER in getattr(obj, "card_types", set())
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Apply Together as One's converge effects."""
        from engine.game import deal_damage, draw_card

        chosen_targets = getattr(self, "chosen_targets", [])
        draw_target = chosen_targets[0] if len(chosen_targets) > 0 else None
        damage_target = chosen_targets[1] if len(chosen_targets) > 1 else None

        colors_spent = getattr(self, "colors_spent", [])
        if isinstance(colors_spent, int):
            x_value = max(0, colors_spent)
        else:
            x_value = len(set(colors_spent))

        for _ in range(x_value):
            if draw_target is not None:
                draw_card(game, draw_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x_value)

        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x_value
