"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _is_any_target(obj: Any) -> bool:
    """A player or a creature (planeswalkers are also legal 'any target')."""
    if _is_player(obj):
        return True
    types = getattr(obj, "card_types", set())
    return CardType.CREATURE in types or CardType.PLANESWALKER in types


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
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        x = len(set(getattr(self, "colors_spent", []) or []))

        chosen = getattr(self, "chosen_targets", None) or [None, None]
        player_target = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None

        if player_target is not None:
            for _ in range(x):
                draw_card(game, player_target)

        if damage_target is not None and x > 0:
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
