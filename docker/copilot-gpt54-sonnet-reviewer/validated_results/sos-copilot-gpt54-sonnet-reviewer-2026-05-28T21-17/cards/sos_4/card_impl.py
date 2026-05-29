"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import GainsLifeTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target_idx(card: Any, idx: int) -> Any:
    """Retrieve the chosen target at *idx* for the resolving spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen and len(chosen) > idx:
        return chosen[idx]
    targets = getattr(card, "_resolve_targets", None)
    if targets and len(targets) > idx:
        return targets[idx]
    if idx == 0:
        return getattr(card, "_resolve_target", None)
    return None


def _converge_count(card: Any) -> int:
    """Return the number of distinct mana colors spent to cast *card*."""
    colors_spent = getattr(card, "colors_spent", 0)
    if isinstance(colors_spent, (list, tuple, set, frozenset)):
        return len(colors_spent)
    return int(colors_spent)


def _is_any_target(obj: Any) -> bool:
    """Return whether *obj* is a legal 'any target' object."""
    card_types = getattr(obj, "card_types", set())
    return (
        hasattr(obj, "life")
        or CardType.CREATURE in card_types
        or CardType.PLANESWALKER in card_types
    )


def _is_still_legal_damage_target(game: "GameState", target: Any) -> bool:
    """Return whether the damage target is still legal on resolution."""
    if target is None:
        return False
    if hasattr(target, "life"):
        return target in game.players
    if not _is_any_target(target):
        return False
    for player in game.players:
        if game.get_battlefield(player).contains(target):
            return True
    return False


class TogetherAsOne(Sorcery):
    """Together as One."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X damage to any target, "
            "and you gain X life, where X is the number of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Choose a player to draw and any target to damage."""
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
        """Apply converge-based draw, damage, and life gain."""
        from engine.game import deal_damage, draw_card

        controller = self.controller
        if controller is None:
            return

        draw_target = _get_chosen_target_idx(self, 0)
        damage_target = _get_chosen_target_idx(self, 1)
        count = _converge_count(self)

        if draw_target in game.players:
            for _ in range(count):
                draw_card(game, draw_target)

        if _is_still_legal_damage_target(game, damage_target):
            deal_damage(game, self, damage_target, count)

        if count > 0:
            controller.life += count
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=count),
            )
