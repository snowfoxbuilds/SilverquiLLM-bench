"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage to
    any target, and you gain X life, where X is the number of colors of mana
    spent to cast this spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            (
                "Converge — Target player draws X cards, Together as One deals X damage "
                "to any target, and you gain X life, where X is the number of colors of "
                "mana spent to cast this spell."
            ),
        )
        super().__init__(**kwargs)
        # Converge: number of colors of mana spent to cast this spell.
        self.colors_spent: int = 0
        # Targets: [draw_target (player), damage_target (any target)]
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return two target requirements: a player (draw) and any target (damage)."""
        from engine.player import Player

        def is_player(obj: Any) -> bool:
            return hasattr(obj, "life") and hasattr(obj, "zones")

        def is_any_target(obj: Any) -> bool:
            # Players or creatures
            if is_player(obj):
                return True
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                return True
            return False

        draw_req = TargetRequirement(
            filter_fn=is_player,
            description="target player (draws X cards)",
            zone=Zone.BATTLEFIELD,
        )
        damage_req = TargetRequirement(
            filter_fn=is_any_target,
            description="any target (deals X damage)",
            zone=Zone.BATTLEFIELD,
        )
        return [draw_req, damage_req]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the spell: draw X cards, deal X damage, gain X life."""
        from engine.game import deal_damage, draw_card

        x = self.colors_spent
        targets = getattr(self, "chosen_targets", [])

        # Determine draw target (first target) and damage target (second target)
        draw_target = targets[0] if len(targets) >= 1 else None
        damage_target = targets[1] if len(targets) >= 2 else None

        # Draw X cards for the draw target
        if x > 0 and draw_target is not None:
            for _ in range(x):
                draw_card(game, draw_target)

        # Deal X damage to the damage target
        if x > 0 and damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # Controller gains X life
        controller = getattr(self, "controller", None)
        if x > 0 and controller is not None:
            controller.life += x
