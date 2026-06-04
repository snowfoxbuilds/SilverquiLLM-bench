"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_any_target(obj: Any) -> bool:
    """Return ``True`` if *obj* is a legal "any target" (creature/planeswalker/player)."""
    if hasattr(obj, "life"):
        return True  # player
    types = getattr(obj, "card_types", set())
    return CardType.CREATURE in types or CardType.PLANESWALKER in types


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and not getattr(obj, "card_types", None)


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
        # Number/list of colors spent to cast.  Set by the casting pipeline
        # (a list of Color) or directly by tests (an int).
        self.colors_spent: Any = 0

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target player (to draw), then any target (to damage)."""
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
        cs = getattr(self, "colors_spent", 0)
        if isinstance(cs, int):
            return cs
        try:
            return len(cs)
        except TypeError:
            return 0

    def on_resolve(self, game: "GameState") -> None:
        """Draw X, deal X damage to any target, gain X life."""
        from engine.game import deal_damage, draw_card

        x = self._converge_x()
        chosen = getattr(self, "chosen_targets", None) or []

        target_player = chosen[0] if len(chosen) >= 1 else None
        damage_target = chosen[1] if len(chosen) >= 2 else None

        if target_player is not None and hasattr(target_player, "life"):
            for _ in range(x):
                draw_card(game, target_player)

        if damage_target is not None and x > 0:
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and x > 0:
            controller.life += x
