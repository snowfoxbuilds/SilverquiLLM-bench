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

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: a player (to draw) and any target (for the damage).

        Order matters — ``chosen_targets[0]`` is the target player and
        ``chosen_targets[1]`` is the damage target.
        """
        def _is_player(obj: Any) -> bool:
            return obj in game.players

        def _is_any_target(obj: Any) -> bool:
            if obj in game.players:
                return True
            types = getattr(obj, "card_types", set())
            return bool(types & {CardType.CREATURE, CardType.PLANESWALKER})

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

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Converge: draw X, deal X, gain X (X = distinct colors spent)."""
        from engine.game import deal_damage, draw_card
        from engine.events import GainsLifeTriggeredEvent

        controller = self.controller
        # X = number of distinct colors of mana spent to cast this spell.
        colors_spent = getattr(self, "colors_spent", [])
        x = len(set(colors_spent))

        chosen = getattr(self, "chosen_targets", None) or []
        target_player = chosen[0] if len(chosen) >= 1 else None
        damage_target = chosen[1] if len(chosen) >= 2 else None

        if x > 0 and target_player is not None:
            for _ in range(x):
                draw_card(game, target_player)

        if x > 0 and damage_target is not None:
            deal_damage(game, self, damage_target, x)

        if x > 0 and controller is not None and hasattr(controller, "life"):
            controller.life += x
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
