"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import DealsDamageTriggeredEvent, GainsLifeTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_colors_spent(value: Any) -> int:
    """Return the distinct-color count recorded for a converge spell."""
    if value is None:
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(set(value))
    return 0


def _is_planeswalker(target: Any) -> bool:
    """Return whether the target is a planeswalker permanent."""
    return CardType.PLANESWALKER in getattr(target, "card_types", set())


class TogetherAsOne(Sorcery):
    """Together as One — target player draws X, any target takes X, you gain X."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X damage "
            "to any target, and you gain X life, where X is the number of colors of "
            "mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        self.colors_spent: int = 0

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return the spell's two targets."""
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
        """Apply the converge-scaled draw, damage, and life gain effects."""
        from engine.game import deal_damage, draw_card
        from engine.protection import has_protection_from

        chosen_targets = getattr(self, "chosen_targets", [])
        draw_target = chosen_targets[0] if len(chosen_targets) >= 1 else None
        damage_target = chosen_targets[1] if len(chosen_targets) >= 2 else None
        x_value = _count_colors_spent(getattr(self, "colors_spent", 0))

        if draw_target is not None and hasattr(draw_target, "zones"):
            for _ in range(x_value):
                draw_card(game, draw_target)

        if damage_target is not None and _is_planeswalker(damage_target):
            if x_value > 0 and not has_protection_from(damage_target, self):
                damage_target.loyalty = max(0, getattr(damage_target, "loyalty", 0) - x_value)
                game.trigger_manager.fire_event(
                    game,
                    DealsDamageTriggeredEvent(source=self, target=damage_target, amount=x_value),
                )
        elif damage_target is not None:
            deal_damage(game, self, damage_target, x_value)

        controller = self.controller
        if controller is not None and x_value > 0:
            controller.life += x_value
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x_value),
            )
