"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.game import deal_damage, draw_card
from engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    """Return True if *obj* behaves like a player."""
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _is_creature(obj: Any) -> bool:
    """Return True if *obj* is a creature permanent/card."""
    return isinstance(obj, Creature)


def _is_on_battlefield(game: "GameState", obj: Any) -> bool:
    """Return True if *obj* is currently on any player's battlefield."""
    return any(game.get_battlefield(player).contains(obj) for player in game.players)


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

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return the target player and any-target requirements."""
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: _is_player(obj) or _is_creature(obj),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Apply the card's converge-scaled draw, damage, and life gain."""
        chosen_targets = getattr(self, "chosen_targets", [])
        if len(chosen_targets) < 2:
            return

        draw_target, damage_target = chosen_targets[0], chosen_targets[1]
        colors_spent = getattr(self, "colors_spent", [])
        x_value = len(set(colors_spent))

        if _is_player(draw_target):
            for _ in range(x_value):
                draw_card(game, draw_target)

        if _is_player(damage_target):
            deal_damage(game, self, damage_target, x_value)
        elif _is_creature(damage_target) and _is_on_battlefield(game, damage_target):
            deal_damage(game, self, damage_target, x_value)

        controller = self.controller
        if controller is not None:
            controller.life += x_value
