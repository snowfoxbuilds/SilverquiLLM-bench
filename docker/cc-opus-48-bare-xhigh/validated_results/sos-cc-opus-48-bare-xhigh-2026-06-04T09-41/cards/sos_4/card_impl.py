"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and not hasattr(obj, "card_types")


def _is_any_target(obj: Any) -> bool:
    if _is_player(obj):
        return True
    types = getattr(obj, "card_types", set())
    return bool(types & {CardType.CREATURE, CardType.PLANESWALKER})


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, this deals X damage to any
    target, and you gain X life, where X is the number of colors of mana
    spent to cast this spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals "
            "X damage to any target, and you gain X life, where X is the "
            "number of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Default for tests that set this directly without the cast pipeline.
        self.colors_spent: Any = 0

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player draws X",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=_is_any_target,
                description="any target takes X damage",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def _converge_x(self) -> int:
        cs = getattr(self, "colors_spent", 0)
        if isinstance(cs, list):
            return len(cs)
        return int(cs)

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import deal_damage, draw_card

        x = self._converge_x()
        targets = getattr(self, "chosen_targets", []) or []
        player_target = targets[0] if len(targets) > 0 else None
        damage_target = targets[1] if len(targets) > 1 else None

        if x > 0 and player_target is not None:
            for _ in range(x):
                draw_card(game, player_target)

        if x > 0 and damage_target is not None:
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
            from engine.events import GainsLifeTriggeredEvent

            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
