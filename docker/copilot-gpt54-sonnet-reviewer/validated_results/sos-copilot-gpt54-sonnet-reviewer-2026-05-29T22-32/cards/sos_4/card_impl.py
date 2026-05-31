"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life")


def _is_any_target(obj: Any) -> bool:
    card_types = getattr(obj, "card_types", set())
    return (
        _is_player(obj)
        or CardType.CREATURE in card_types
        or CardType.PLANESWALKER in card_types
    )


def _converge_value(card: Any) -> int:
    colors_spent = getattr(card, "colors_spent", 0)
    if isinstance(colors_spent, int):
        return max(0, colors_spent)
    if colors_spent is None:
        return 0
    try:
        return len(set(colors_spent))
    except TypeError:
        return 0


class TogetherAsOne(Sorcery):
    """Together as One."""

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
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=_is_any_target,
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import deal_damage, draw_card, gain_life

        chosen_targets = list(getattr(self, "chosen_targets", []) or [])
        draw_target = chosen_targets[0] if len(chosen_targets) > 0 else None
        damage_target = chosen_targets[1] if len(chosen_targets) > 1 else None

        x_value = _converge_value(self)

        if _is_player(draw_target):
            for _ in range(x_value):
                draw_card(game, draw_target)

        if damage_target is not None and _is_any_target(damage_target):
            deal_damage(game, self, damage_target, x_value)

        controller = self.controller
        if controller is not None:
            gain_life(game, controller, x_value)
