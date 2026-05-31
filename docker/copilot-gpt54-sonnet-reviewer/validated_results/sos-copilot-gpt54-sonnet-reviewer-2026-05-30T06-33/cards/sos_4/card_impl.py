"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import GainsLifeTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — Converge draw, damage, and life gain."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X damage "
            "to any target, and you gain X life, where X is the number of colors of "
            "mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def _x_value(self) -> int:
        """Return X from the spell's converge payment history."""
        return len(set(getattr(self, "colors_spent", []) or []))

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a player to draw and a separate damage target."""
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
                    or CardType.PLANESWALKER in getattr(obj, "card_types", set())
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Apply Together as One's three converge-scaled effects."""
        from engine.game import deal_damage, draw_card

        chosen = getattr(self, "chosen_targets", []) or []
        if len(chosen) < 2:
            return

        draw_target = chosen[0]
        damage_target = chosen[1]
        x_value = self._x_value()

        if draw_target is not None:
            for _ in range(x_value):
                draw_card(game, draw_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x_value)

        controller = self.controller
        if controller is None or x_value <= 0:
            return

        controller.life += x_value
        if hasattr(game, "trigger_manager"):
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x_value),
            )
