"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import GainsLifeTriggeredEvent
from engine.game import deal_damage, draw_card
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    """Return True when *obj* behaves like a player."""
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_any_target(obj: Any) -> bool:
    """Return True when *obj* is a legal 'any target' choice for this engine."""
    card_types = getattr(obj, "card_types", set())
    return _is_player(obj) or CardType.CREATURE in card_types


class TogetherAsOne(Sorcery):
    """Together as One — Converge sorcery that draws, deals damage, and gains life."""

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
        """Choose a player to draw and a separate any-target for damage."""
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

    def _converge_count(self) -> int:
        """Return the number of distinct colors of mana spent to cast this spell."""
        colors_spent = getattr(self, "colors_spent", [])
        if isinstance(colors_spent, int):
            return max(0, colors_spent)
        try:
            return len(colors_spent)
        except TypeError:
            return 0

    def on_resolve(self, game: "GameState") -> None:
        """Apply Together as One's converge-scaled effects."""
        x = self._converge_count()
        chosen_targets = getattr(self, "chosen_targets", []) or []
        player_target = chosen_targets[0] if len(chosen_targets) >= 1 else None
        damage_target = chosen_targets[1] if len(chosen_targets) >= 2 else None

        if _is_player(player_target):
            for _ in range(x):
                draw_card(game, player_target)

        if _is_player(damage_target):
            deal_damage(game, self, damage_target, x)
        elif (
            CardType.CREATURE in getattr(damage_target, "card_types", set())
            and _is_on_battlefield(game, damage_target)
        ):
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x),
            )
