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
        # colors_spent is set by the casting engine as list[Color] after payment.
        self.colors_spent: Any = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Requires two targets: target player, and any target (player or creature)."""
        from engine.player import Player

        def _is_player(obj: Any) -> bool:
            return isinstance(obj, Player)

        def _is_any_target(obj: Any) -> bool:
            if isinstance(obj, Player):
                return True
            return CardType.CREATURE in getattr(obj, "card_types", set())

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
        """Apply converge effects."""
        from engine.game import deal_damage, draw_card

        controller = self.controller
        if controller is None:
            return

        # X = number of distinct colors spent
        colors = self.colors_spent
        if isinstance(colors, list):
            x = len(set(colors))
        elif isinstance(colors, int):
            x = colors
        else:
            x = 0

        if x <= 0:
            return

        targets = getattr(self, "chosen_targets", None) or []
        target_player = targets[0] if len(targets) > 0 else None
        damage_target = targets[1] if len(targets) > 1 else None

        # Target player draws X cards.
        if target_player is not None:
            for _ in range(x):
                draw_card(game, target_player)

        # Deal X damage to any target.
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # You gain X life.
        controller.life += x

