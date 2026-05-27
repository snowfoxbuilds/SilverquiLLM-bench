"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import GainsLifeTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_colors_spent(card: Any) -> int:
    """Return the distinct-color count recorded for a converge spell."""
    colors_spent = getattr(card, "colors_spent", 0)
    if isinstance(colors_spent, int):
        return max(0, colors_spent)
    if colors_spent is None:
        return 0
    try:
        return len(set(colors_spent))
    except TypeError:
        return 0


def _is_any_target(obj: Any) -> bool:
    return hasattr(obj, "life") or CardType.CREATURE in getattr(obj, "card_types", set())


def _is_still_legal_target(game: "GameState", target: Any, requirement: TargetRequirement) -> bool:
    """Recheck legality on resolution for independently targeted effects."""
    if target is None or not requirement.filter_fn(target):
        return False
    if hasattr(target, "life"):
        return True
    for player in game.players:
        if any(obj is target for obj in player.zones[requirement.zone].get_all()):
            return True
    return False


class TogetherAsOne(Sorcery):
    """Together as One."""

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

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target a player to draw cards and any target to take damage."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
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
        """Apply Together as One's three linked converge effects."""
        from engine.game import deal_damage, draw_card

        controller = self.controller
        if controller is None:
            return

        x_value = _count_colors_spent(self)
        chosen_targets = list(getattr(self, "chosen_targets", []))
        requirements = self.get_targets(game)

        draw_target = chosen_targets[0] if len(chosen_targets) > 0 else None
        damage_target = chosen_targets[1] if len(chosen_targets) > 1 else None

        draw_target_is_legal = _is_still_legal_target(game, draw_target, requirements[0])
        damage_target_is_legal = _is_still_legal_target(game, damage_target, requirements[1])

        if not draw_target_is_legal and not damage_target_is_legal:
            return

        if draw_target_is_legal:
            for _ in range(x_value):
                draw_card(game, draw_target)

        if damage_target_is_legal:
            deal_damage(game, self, damage_target, x_value)

        if x_value > 0:
            controller.life += x_value
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x_value),
            )
