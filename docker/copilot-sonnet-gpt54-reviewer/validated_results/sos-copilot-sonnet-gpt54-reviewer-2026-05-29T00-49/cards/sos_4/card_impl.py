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
        # colors_spent is set by the casting system or test code before resolve
        self.colors_spent: list[Any] = []
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: target player, then any target (player or creature)."""
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
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the converge effect."""
        from engine.game import deal_damage, draw_card, gain_life

        chosen = getattr(self, "chosen_targets", [])
        if len(chosen) < 2:
            return

        draw_target = chosen[0]   # player who draws cards
        damage_target = chosen[1]  # player or creature that receives damage

        # X = number of distinct colors of mana spent
        colors_spent = getattr(self, "colors_spent", [])
        x = len(set(colors_spent))

        # 1. Target player draws X cards
        if x > 0 and hasattr(draw_target, "zones"):
            for _ in range(x):
                draw_card(game, draw_target)

        # 2. Deal X damage to any target — revalidate creature targets first
        if x > 0:
            damage_target_valid = True
            if hasattr(damage_target, "damage_marked"):
                # damage_target is a creature; check it's still on the battlefield
                on_battlefield = any(
                    game.get_battlefield(p).contains(damage_target)
                    for p in game.players
                )
                if not on_battlefield:
                    damage_target_valid = False
            if damage_target_valid:
                deal_damage(game, self, damage_target, x)

        # 3. Casting player (controller) gains X life
        if x > 0:
            caster = self.controller
            if caster is not None:
                gain_life(game, caster, x)
