"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Planeswalker, Sorcery
from engine.types import CardType, Color, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and not hasattr(obj, "card_types")


def _is_any_target(obj: Any) -> bool:
    if _is_player(obj):
        return True
    card_types = getattr(obj, "card_types", set())
    return (
        CardType.CREATURE in card_types
        or CardType.PLANESWALKER in card_types
        or isinstance(obj, Planeswalker)
    )


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

    def _get_converge_value(self) -> int:
        colors_spent = getattr(self, "colors_spent", [])
        if isinstance(colors_spent, int):
            return max(0, colors_spent)
        if colors_spent is None:
            return 0
        try:
            normalized = {color for color in colors_spent if isinstance(color, Color)}
            return len(normalized)
        except TypeError:
            return 0

    def on_resolve(self, game: "GameState") -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        chosen_targets = getattr(self, "chosen_targets", None)
        if not chosen_targets or len(chosen_targets) < 2:
            return

        x_value = self._get_converge_value()
        if x_value <= 0:
            return

        draw_target = chosen_targets[0]
        damage_target = chosen_targets[1]

        if _is_player(draw_target):
            for _ in range(x_value):
                draw_card(game, draw_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x_value)

        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x_value
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x_value),
            )
