"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number of "
            "colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Set by the casting pipeline from mana_pool.last_payment_colors
        self.colors_spent: list = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: a player, then any target (creature/player/planeswalker)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj in game.players,
                description="target player (draws cards)",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: (
                    obj in game.players
                    or CardType.CREATURE in getattr(obj, "card_types", set())
                    or CardType.PLANESWALKER in getattr(obj, "card_types", set())
                ),
                description="any target (deals damage)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Converge: draw X, deal X, gain X where X = distinct colors spent."""
        from engine.game import deal_damage, draw_card

        controller = self.controller
        if controller is None:
            return

        # X = number of distinct colors of mana spent to cast
        colors_spent = getattr(self, "colors_spent", [])
        x = len(colors_spent)
        if x == 0:
            return

        chosen = getattr(self, "chosen_targets", None) or []

        # Target player draws X cards
        target_player = chosen[0] if chosen else None
        if target_player is not None and target_player in game.players:
            for _ in range(x):
                draw_card(game, target_player)

        # Deal X damage to any target
        damage_target = chosen[1] if len(chosen) > 1 else None
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # You gain X life
        controller.life += x

