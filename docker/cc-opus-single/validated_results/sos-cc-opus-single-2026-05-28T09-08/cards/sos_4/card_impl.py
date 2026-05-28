"""Card implementation for Together as One (SOS #4).

Together as One is a {6} sorcery with Converge:
  Target player draws X cards, Together as One deals X damage to any target,
  and you gain X life, where X is the number of colors of mana spent to cast
  this spell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One -- {6} -- Sorcery.

    Converge -- Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.
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
        # Converge tracking: can be an int or a list of Color enums.
        self.colors_spent: int | list[Any] = 0

    def _get_x(self) -> int:
        """Derive X from colors_spent (int or list of Color enums)."""
        cs = self.colors_spent
        if isinstance(cs, int):
            return cs
        # If it's a list (e.g. [Color.WHITE, Color.BLUE, Color.RED]),
        # X = number of distinct colors.
        return len(set(cs))

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        """Return two target requirements: 'target player' and 'any target'."""

        def _is_player(obj: Any) -> bool:
            """Accept any object that has a 'life' attribute (i.e. a player)."""
            return hasattr(obj, "life")

        def _is_any_target(obj: Any) -> bool:
            """Accept a player or a creature (any target)."""
            if hasattr(obj, "life"):
                return True
            if hasattr(obj, "card_types") and CardType.CREATURE in obj.card_types:
                return True
            # Also accept planeswalkers
            if hasattr(obj, "card_types") and CardType.PLANESWALKER in obj.card_types:
                return True
            return False

        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=_is_any_target,
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve: draw X, deal X damage, gain X life."""
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        x = self._get_x()
        targets = getattr(self, "chosen_targets", None) or []

        # Target 0: target player (draws X cards)
        if len(targets) >= 1:
            draw_target = targets[0]
            if draw_target is not None and hasattr(draw_target, "life"):
                for _ in range(x):
                    draw_card(game, draw_target)

        # Target 1: any target (takes X damage)
        if len(targets) >= 2:
            damage_target = targets[1]
            if damage_target is not None:
                deal_damage(game, self, damage_target, x)

        # Controller gains X life
        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
