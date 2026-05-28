"""Card implementation for Together as One (SOS #4).

Together as One is a {6} Converge Sorcery:
  Converge — Target player draws X cards, Together as One deals X damage to
  any target, and you gain X life, where X is the number of colors of mana
  spent to cast this spell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Converge Sorcery.

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
        # Tracks distinct colors of mana spent to cast (set externally by cast
        # logic or test code — mirrors the FDN 205 Wardens of the Cycle pattern).
        self.colors_spent: int = 0

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return two targeting requirements: draw target and damage target."""
        return [
            {"description": "target player (draw)", "zone": "player"},
            {"description": "any target (damage)", "zone": "any"},
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve all three Converge effects using colors_spent as X.

        chosen_targets[0] — the player who draws X cards.
        chosen_targets[1] — the player or creature that takes X damage.
        The controller (self.controller) gains X life.
        """
        from engine.game import deal_damage, draw_card
        from engine.events import GainsLifeTriggeredEvent

        x = self.colors_spent
        if x <= 0:
            return

        chosen = getattr(self, "chosen_targets", None) or []

        # Effect 1: target player draws X cards.
        draw_target = chosen[0] if len(chosen) >= 1 else None
        if draw_target is not None and hasattr(draw_target, "zones"):
            for _ in range(x):
                draw_card(game, draw_target)

        # Effect 2: deal X damage to any target (player or creature).
        damage_target = chosen[1] if len(chosen) >= 2 else None
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # Effect 3: casting player gains X life.
        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
            if hasattr(game, "trigger_manager"):
                game.trigger_manager.fire_event(
                    game,
                    GainsLifeTriggeredEvent(player=controller, amount=x),
                )
