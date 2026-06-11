"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X
    damage to any target, and you gain X life, where X is the number of
    colors of mana spent to cast this spell.

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

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: a player, then any target (creature/planeswalker/player)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life")
                or bool(
                    getattr(obj, "card_types", set())
                    & {CardType.CREATURE, CardType.PLANESWALKER}
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Draw X / deal X / gain X, where X = colors of mana spent."""
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        # colors_spent is recorded at cast time as the distinct colors paid.
        x = len(set(getattr(self, "colors_spent", []) or []))
        if x <= 0:
            return

        chosen = getattr(self, "chosen_targets", None) or []
        draw_target = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None

        if draw_target is not None and hasattr(draw_target, "life"):
            for _ in range(x):
                draw_card(game, draw_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None:
            controller.life += x
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
