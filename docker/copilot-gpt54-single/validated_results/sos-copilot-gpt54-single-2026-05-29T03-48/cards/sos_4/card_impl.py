"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Color, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: "GameState", obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_any_target(obj: Any) -> bool:
    """Return ``True`` if *obj* is a player, creature, or planeswalker."""
    if hasattr(obj, "life"):
        return True

    card_types = getattr(obj, "card_types", set())
    return bool(card_types & {CardType.CREATURE, CardType.PLANESWALKER})


def _is_legal_damage_target(game: "GameState", obj: Any) -> bool:
    """Return ``True`` if *obj* is still a legal ``any target`` target."""
    if obj is None:
        return False
    if hasattr(obj, "life"):
        return obj in game.players
    if not _is_on_battlefield(game, obj):
        return False
    return _is_any_target(obj)


class TogetherAsOne(Sorcery):
    """Together as One — converge value spell."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X damage "
            "to any target, and you gain X life, where X is the number of colors "
            "of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target one player and one any-target object."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
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
        """Apply the converge draw, damage, and life-gain effects."""
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        chosen_targets = getattr(self, "chosen_targets", [])
        target_player = chosen_targets[0] if len(chosen_targets) > 0 else None
        damage_target = chosen_targets[1] if len(chosen_targets) > 1 else None

        x = len({
            color for color in getattr(self, "colors_spent", [])
            if isinstance(color, Color)
        })

        if x <= 0:
            return

        if target_player is not None and hasattr(target_player, "life"):
            for _ in range(x):
                draw_card(game, target_player)

        if _is_legal_damage_target(game, damage_target):
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x),
            )
