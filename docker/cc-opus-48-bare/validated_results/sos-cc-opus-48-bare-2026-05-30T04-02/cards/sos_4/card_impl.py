"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target_idx(card: Any, idx: int) -> Any:
    """Retrieve the *idx*-th chosen target for a spell (0-indexed)."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen and len(chosen) > idx:
        return chosen[idx]
    targets = getattr(card, "_resolve_targets", None)
    if targets and len(targets) > idx:
        return targets[idx]
    return None


def _converge_count(card: Any) -> int:
    """Return the number of colors of mana spent to cast *card*.

    The casting pipeline stores ``colors_spent`` as a list of colors; tests
    may set it as an int count directly.  Both forms are supported.
    """
    spent = getattr(card, "colors_spent", None)
    if spent is None:
        return 0
    if isinstance(spent, int):
        return spent
    return len(spent)


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
            "Converge — Target player draws X cards, Together as One deals "
            "X damage to any target, and you gain X life, where X is the "
            "number of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: a player (to draw) and any target (for damage)."""
        players = list(game.players)

        def _is_player(obj: Any) -> bool:
            return obj in players

        def _is_any_target(obj: Any) -> bool:
            if obj in players:
                return True
            types = getattr(obj, "card_types", set())
            return CardType.CREATURE in types or CardType.PLANESWALKER in types

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
        """Converge: draw X, deal X damage, gain X life."""
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        x = _converge_count(self)
        if x <= 0:
            return

        draw_target = _get_chosen_target_idx(self, 0)
        damage_target = _get_chosen_target_idx(self, 1)
        controller = self.controller

        if draw_target is not None:
            for _ in range(x):
                draw_card(game, draw_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        if controller is not None:
            controller.life += x
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=x)
            )
