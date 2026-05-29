"""Card implementation for Together as One (SOS #4).

Oracle text:
  Converge — Target player draws X cards, Together as One deals X damage to
  any target, and you gain X life, where X is the number of colors of mana
  spent to cast this spell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
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
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # colors_spent is set by casting logic or tests to track converge value.
        # Can be a list of Color values or an int.
        self.colors_spent: list | int = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return two target requirements: one for drawing (player) and one for damage (any)."""
        from engine.card import Creature

        draw_req = TargetRequirement(
            filter_fn=lambda obj: hasattr(obj, "life"),
            description="target player",
            zone=Zone.BATTLEFIELD,
        )
        damage_req = TargetRequirement(
            filter_fn=lambda obj: hasattr(obj, "life") or CardType.CREATURE in getattr(obj, "card_types", set()),
            description="any target",
            zone=Zone.BATTLEFIELD,
        )
        return [draw_req, damage_req]

    def on_resolve(self, game: "GameState") -> None:
        """Apply converge effects: draw X, deal X damage, gain X life."""
        from engine.game import deal_damage, draw_card
        from engine.events import GainsLifeTriggeredEvent

        # Compute X from colors_spent
        colors = self.colors_spent
        if isinstance(colors, int):
            x = colors
        else:
            x = len(colors)

        if x <= 0:
            return

        chosen = getattr(self, "chosen_targets", None)
        if not chosen or len(chosen) < 2:
            return

        draw_target = chosen[0]
        damage_target = chosen[1]
        controller = self.controller

        # 1. Target player draws X cards
        if hasattr(draw_target, "zones"):
            for _ in range(x):
                draw_card(game, draw_target)

        # 2. Deal X damage to any target
        deal_damage(game, self, damage_target, x)

        # 3. Controller gains X life
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x),
            )
