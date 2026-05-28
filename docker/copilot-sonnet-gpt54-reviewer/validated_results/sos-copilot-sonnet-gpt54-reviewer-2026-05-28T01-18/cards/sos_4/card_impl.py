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
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Converge: tracks how many distinct colors of mana were spent to cast
        # this spell. Set externally by cast logic or test setup.
        self.colors_spent: int = 0

    def get_targets(self, game: "GameState") -> list:
        """Declare two mandatory targets: a target player and any target."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "zones"),
                description="target player",
                zone=Zone.NONE,
            ),
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="any target",
                zone=Zone.NONE,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: draw X, deal X damage, gain X life (X = colors_spent)."""
        from engine.game import deal_damage, draw_card

        # Normalize colors_spent: may be an int (set in tests) or a list of
        # colors (set by the casting engine via mana_pool.last_payment_colors).
        raw = self.colors_spent
        if isinstance(raw, list):
            x = len(set(raw))
        else:
            x = int(raw)

        chosen = getattr(self, "chosen_targets", None) or []

        # chosen_targets[0] = target player who draws cards
        # chosen_targets[1] = any target (player or creature) that takes damage
        draw_target = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None

        # 1. Target player draws X cards
        if draw_target is not None and x > 0:
            for _ in range(x):
                draw_card(game, draw_target)

        # 2. Deal X damage to any target
        if damage_target is not None and x > 0:
            deal_damage(game, self, damage_target, x)

        # 3. Caster gains X life
        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
