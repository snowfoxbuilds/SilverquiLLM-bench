"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _distinct_colors_spent(colors_spent: Any) -> int:
    """Return the number of distinct colors represented by ``colors_spent``."""
    if not colors_spent:
        return 0

    if isinstance(colors_spent, int):
        return max(0, colors_spent)

    distinct: set[str] = set()
    for color in colors_spent:
        value = getattr(color, "value", color)
        if value in {"W", "U", "B", "R", "G"}:
            distinct.add(value)
    return len(distinct)


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class TogetherAsOne(Sorcery):
    """Together as One — converged draw, damage, and life gain sorcery."""

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
        self.colors_spent: int | list[Any] = 0

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return target player and any-target requirements."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life")
                or CardType.CREATURE in getattr(obj, "card_types", set()),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Target player draws X, any target takes X, you gain X."""
        from engine.game import deal_damage, draw_card

        chosen = getattr(self, "chosen_targets", None)
        if not chosen or len(chosen) < 2:
            return

        cards_target = chosen[0]
        damage_target = chosen[1]
        x_value = _distinct_colors_spent(getattr(self, "colors_spent", 0))
        if x_value <= 0:
            return

        if hasattr(cards_target, "life"):
            for _ in range(x_value):
                draw_card(game, cards_target)

        if hasattr(damage_target, "life"):
            deal_damage(game, self, damage_target, x_value)
        elif hasattr(damage_target, "damage_marked") and _is_on_battlefield(game, damage_target):
            deal_damage(game, self, damage_target, x_value)

        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x_value
