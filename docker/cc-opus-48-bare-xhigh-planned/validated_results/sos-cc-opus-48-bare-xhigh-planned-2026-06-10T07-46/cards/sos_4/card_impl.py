"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.player import Player
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return isinstance(obj, Player)


def _is_any_target(obj: Any) -> bool:
    """A creature, player, or planeswalker (rule 115.4 — no battles in engine)."""
    if isinstance(obj, Player):
        return True
    types = getattr(obj, "card_types", set())
    return bool(types & {CardType.CREATURE, CardType.PLANESWALKER})


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
        # Set by the cast pipeline to the list of distinct colors spent.
        self.colors_spent: list = []

    def get_targets(self, game: "GameState") -> list:
        """Two targets: a target player (draws), and any target (damage)."""
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

    def _converge_x(self) -> int:
        """X = number of distinct colors of mana spent to cast this spell.

        The cast pipeline sets ``colors_spent`` to a list of Color; tests may
        set it to an int count directly (the fdn_205 convention).  Handle both.
        """
        cs = getattr(self, "colors_spent", [])
        if isinstance(cs, int):
            return cs
        return len(set(cs))

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import deal_damage, draw_card

        x = self._converge_x()
        targets = getattr(self, "chosen_targets", []) or []
        target_player = targets[0] if len(targets) >= 1 else None
        any_target = targets[1] if len(targets) >= 2 else None

        # Target player draws X cards.
        if target_player is not None and x > 0:
            for _ in range(x):
                draw_card(game, target_player)

        # Deal X damage to any target.
        if any_target is not None and x > 0:
            deal_damage(game, self, any_target, x)

        # You gain X life.
        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
