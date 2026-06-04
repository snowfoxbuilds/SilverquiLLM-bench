"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _colors_spent_count(card: Any) -> int:
    """Return the converge count from ``colors_spent`` (list of Color or int)."""
    cs = getattr(card, "colors_spent", 0)
    if isinstance(cs, list):
        return len(cs)
    return cs or 0


def _is_any_target(obj: Any) -> bool:
    """Return True if *obj* is a legal "any target" (player/creature/planeswalker)."""
    if hasattr(obj, "life"):
        return True
    card_types = getattr(obj, "card_types", set())
    return bool(card_types & {CardType.CREATURE, CardType.PLANESWALKER})


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
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
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

    def on_resolve(self, game: GameState) -> None:
        from engine.game import deal_damage, draw_card

        controller = self.controller
        x = _colors_spent_count(self)

        chosen = getattr(self, "chosen_targets", None) or []
        target_player = chosen[0] if len(chosen) > 0 else None
        any_target = chosen[1] if len(chosen) > 1 else None

        if target_player is not None and hasattr(target_player, "life"):
            for _ in range(x):
                draw_card(game, target_player)

        if any_target is not None and x > 0:
            deal_damage(game, self, any_target, x)

        if controller is not None:
            controller.life += x
