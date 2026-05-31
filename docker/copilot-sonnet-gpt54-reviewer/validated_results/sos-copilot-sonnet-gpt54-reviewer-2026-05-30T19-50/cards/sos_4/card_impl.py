"""Card implementation for Together as One (SOS #4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

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
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Default colors_spent for when card is used without the cast pipeline.
        self.colors_spent: Any = 0

    def _get_x(self) -> int:
        """Return X = number of distinct colors of mana spent to cast this spell."""
        cs = getattr(self, "colors_spent", 0)
        if isinstance(cs, (list, tuple)):
            return len(cs)
        return int(cs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: target player (draw), any target (damage)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") and hasattr(obj, "zones"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    or CardType.PLANESWALKER in getattr(obj, "card_types", set())
                    or (hasattr(obj, "life") and hasattr(obj, "zones"))
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Draw X cards for target player, deal X damage, gain X life."""
        from engine.game import deal_damage, draw_card

        x = self._get_x()

        chosen = getattr(self, "chosen_targets", None) or []
        draw_target = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None
        controller = self.controller

        # Target player draws X cards.
        if draw_target is not None and x > 0:
            for _ in range(x):
                draw_card(game, draw_target)

        # Deal X damage to any target.
        if damage_target is not None and x > 0:
            deal_damage(game, self, damage_target, x)

        # You gain X life.
        if controller is not None and x > 0:
            controller.life += x
