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

    def get_targets(self, game: GameState) -> list[Any]:
        """Two targets: target player, then any target (creature or player)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    or hasattr(obj, "life")
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        x = len(set(getattr(self, "colors_spent", []) or []))

        chosen = getattr(self, "chosen_targets", None) or []
        draw_target = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None

        if draw_target is not None and hasattr(draw_target, "life"):
            for _ in range(x):
                draw_card(game, draw_target)

        if damage_target is not None and x > 0:
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
