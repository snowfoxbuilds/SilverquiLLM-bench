"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _converge_count(card: Any) -> int:
    """Return the number of distinct colors of mana spent to cast *card*."""
    colors_spent = getattr(card, "colors_spent", [])
    if isinstance(colors_spent, int):
        return max(0, colors_spent)
    return len(set(colors_spent))


def _is_any_target(obj: Any) -> bool:
    """Return whether *obj* is a legal ``any target`` choice in this engine."""
    card_types = getattr(obj, "card_types", set())
    return (
        hasattr(obj, "life")
        or CardType.CREATURE in card_types
        or CardType.PLANESWALKER in card_types
    )


def _is_on_battlefield(game: "GameState", obj: Any) -> bool:
    """Return whether *obj* is currently on a battlefield."""
    return any(game.get_battlefield(player).contains(obj) for player in game.players)


def _damage_target_is_still_legal(game: "GameState", target: Any) -> bool:
    """Revalidate the spell's damage target on resolution."""
    if target is None or not _is_any_target(target):
        return False
    if hasattr(target, "life"):
        return True
    return _is_on_battlefield(game, target)


def _deal_damage_to_any_target(game: "GameState", source: Any, target: Any, amount: int) -> None:
    """Deal damage to a player, creature, or planeswalker target."""
    from engine.game import deal_damage

    if amount <= 0 or target is None:
        return
    if CardType.PLANESWALKER in getattr(target, "card_types", set()):
        target.loyalty = max(0, getattr(target, "loyalty", 0) - amount)
        return
    deal_damage(game, source, target, amount)


class TogetherAsOne(Sorcery):
    """Together as One — converged draw, damage, and life gain spell."""

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

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target one player, then one creature or player."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life") and not hasattr(obj, "damage_marked"),
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
        """Apply all three converge effects using the same X."""
        from engine.game import draw_card

        chosen_targets = getattr(self, "chosen_targets", None) or []
        if len(chosen_targets) < 2:
            return

        draw_target, damage_target = chosen_targets[0], chosen_targets[1]
        x = _converge_count(self)
        controller = self.controller or self.owner
        if controller is None:
            return

        for _ in range(x):
            draw_card(game, draw_target)
        if _damage_target_is_still_legal(game, damage_target):
            _deal_damage_to_any_target(game, self, damage_target, x)
        controller.life += x
