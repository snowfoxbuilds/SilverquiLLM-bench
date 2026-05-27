"""Card implementation for Together as One (SOS #4).

Converge — Target player draws X cards, Together as One deals X damage to
any target, and you gain X life, where X is the number of colors of mana
spent to cast this spell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import GainsLifeTriggeredEvent
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
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Tracks how many distinct colors of mana were spent to cast this spell.
        # Set externally by the casting pipeline or test setup.
        self.colors_spent: int = 0

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return two TargetRequirements: a player to draw, and any target for damage."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") and not hasattr(obj, "damage_marked"),
                description="target player (draws X cards)",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") or hasattr(obj, "damage_marked"),
                description="any target (deals X damage)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: draw X, deal X damage to any target, controller gains X life."""
        from engine.game import deal_damage, draw_card

        # Normalize colors_spent: may be a list of Color objects or already an int
        raw = self.colors_spent
        if isinstance(raw, (list, tuple, set)):
            x = len(set(raw))
        else:
            x = int(raw)
        targets = getattr(self, "chosen_targets", [])

        draw_target = targets[0] if len(targets) > 0 else None
        damage_target = targets[1] if len(targets) > 1 else None

        # Draw X cards
        if x > 0 and draw_target is not None and hasattr(draw_target, "zones"):
            for _ in range(x):
                draw_card(game, draw_target)

        # Deal X damage to any target
        if x > 0 and damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # Controller gains X life
        controller = self.controller
        if x > 0 and controller is not None and hasattr(controller, "life"):
            controller.life += x
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
