"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(game: "GameState", obj: Any) -> bool:
    return obj in game.players


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


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
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Two targets: a target player (draws X), and any target (damage)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: _is_player(game, obj),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: _is_player(game, obj) or _is_creature(obj),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Converge: X = number of distinct colors of mana spent."""
        from engine.game import deal_damage, draw_card

        colors = getattr(self, "colors_spent", [])
        x = len(set(colors))

        chosen = getattr(self, "chosen_targets", []) or []
        target_player = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None
        controller = self.controller

        # Target player draws X cards.
        if target_player is not None and target_player in game.players:
            for _ in range(x):
                draw_card(game, target_player)

        # Deal X damage to any target (no-op at X = 0).
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # You gain X life.
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
