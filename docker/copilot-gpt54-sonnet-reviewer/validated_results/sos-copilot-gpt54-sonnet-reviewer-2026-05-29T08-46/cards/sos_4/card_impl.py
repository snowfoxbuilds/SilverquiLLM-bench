"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import GainsLifeTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, index: int) -> Any:
    """Return a chosen target by index from the normal resolve pipeline."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen and len(chosen) > index:
        return chosen[index]
    return None


class TogetherAsOne(Sorcery):
    """Together as One."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X damage to any target, "
            "and you gain X life, where X is the number of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
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

    def on_resolve(self, game: GameState) -> None:
        from engine.game import deal_damage, draw_card

        controller = self.controller
        if controller is None:
            return

        x = len(set(getattr(self, "colors_spent", [])))
        draw_target = _get_chosen_target(self, 0)
        damage_target = _get_chosen_target(self, 1)

        if draw_target is not None:
            for _ in range(x):
                draw_card(game, draw_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        if x > 0:
            controller.life += x
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x),
            )
