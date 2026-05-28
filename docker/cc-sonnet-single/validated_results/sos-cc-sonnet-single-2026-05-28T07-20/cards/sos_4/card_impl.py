"""Card implementation for Together as One (SOS 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import GainsLifeTriggeredEvent
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage to
    any target, and you gain X life, where X is the number of colors of mana
    spent to cast this spell.

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
        # Converge: number of distinct colors of mana spent to cast this spell.
        # Defaults to 0; set by the casting pipeline or test code.
        self.colors_spent: int = 0
        # Targets: [draw_target (player), damage_target (player or creature)]
        self.chosen_targets: list[Any] = []

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the Converge spell.

        chosen_targets[0]: the player who draws X cards.
        chosen_targets[1]: any target (player or creature) that takes X damage.
        Controller gains X life.
        """
        from engine.game import deal_damage, draw_card

        x = self.colors_spent
        if x <= 0:
            return

        targets = getattr(self, "chosen_targets", [])

        # Draw X cards for the target player
        if targets:
            draw_target = targets[0]
            for _ in range(x):
                draw_card(game, draw_target)

        # Deal X damage to the damage target
        if len(targets) >= 2:
            damage_target = targets[1]
            deal_damage(game, self, damage_target, x)

        # Controller gains X life
        controller = self.controller
        if controller is not None:
            controller.life += x
            game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=controller, amount=x))
