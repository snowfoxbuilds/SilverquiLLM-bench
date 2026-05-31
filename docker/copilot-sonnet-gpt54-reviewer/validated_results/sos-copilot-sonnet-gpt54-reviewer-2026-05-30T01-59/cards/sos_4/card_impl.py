"""Card implementation for Together as One (SOS #4).

Converge — Target player draws X cards, Together as One deals X damage to
any target, and you gain X life, where X is the number of colors of mana
spent to cast this spell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_target(card: Any, idx: int) -> Any:
    """Return the *idx*-th chosen target, supporting both pipeline and test modes."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen and len(chosen) > idx:
        return chosen[idx]
    targets = getattr(card, "_resolve_targets", None)
    if targets and len(targets) > idx:
        return targets[idx]
    if idx == 0:
        return getattr(card, "_resolve_target", None)
    return None


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        # Converge is a mechanic label, not an evergreen keyword enum value
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Set by the cast pipeline as a list[Color], or directly as int in tests.
        self.colors_spent: Any = 0

    def _converge_x(self) -> int:
        """Return X — the number of distinct colors spent to cast this spell."""
        cs = self.colors_spent
        if isinstance(cs, (list, tuple, set)):
            return len(cs)
        return int(cs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return two target requirements: a player and any target."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "life")
                    or hasattr(obj, "damage_marked")
                ),
                description="any target (creature or player)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Converge effects: draw, damage, life gain."""
        from engine.game import deal_damage, draw_card

        x = self._converge_x()

        controller = self.controller

        # Effect 1: Target player draws X cards.
        draw_target = _get_target(self, 0)
        if draw_target is not None and hasattr(draw_target, "life") and x > 0:
            for _ in range(x):
                draw_card(game, draw_target)

        # Effect 2: Deal X damage to any target.
        damage_target = _get_target(self, 1)
        if damage_target is not None and x > 0:
            deal_damage(game, self, damage_target, x)

        # Effect 3: You (controller) gain X life.
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
