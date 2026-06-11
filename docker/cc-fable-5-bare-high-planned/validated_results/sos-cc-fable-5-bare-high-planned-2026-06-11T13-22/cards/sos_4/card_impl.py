"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _is_any_target(obj: Any) -> bool:
    """'Any target' — a player or a creature (damageable object)."""
    return _is_player(obj) or hasattr(obj, "damage_marked")


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.

    SOS collector number 4.
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

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
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
        from engine.game import deal_damage, draw_card

        x = len(set(getattr(self, "colors_spent", []) or []))

        targets = getattr(self, "chosen_targets", []) or []
        target_player = targets[0] if len(targets) > 0 else None
        any_target = targets[1] if len(targets) > 1 else None

        if target_player is not None:
            for _ in range(x):
                draw_card(game, target_player)

        if any_target is not None:
            deal_damage(game, self, any_target, x)  # no-op when x == 0

        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
