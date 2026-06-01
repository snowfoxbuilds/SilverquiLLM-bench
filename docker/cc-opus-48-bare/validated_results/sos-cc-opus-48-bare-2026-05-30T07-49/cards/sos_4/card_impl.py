"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_any_target(obj: Any) -> bool:
    """Return ``True`` if *obj* is a legal "any target" (creature or player)."""
    return CardType.CREATURE in getattr(obj, "card_types", set()) or hasattr(obj, "life")


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
        # Number of colors of mana spent to cast it.  Set during the cast
        # pipeline (as a list of colors) or directly by tests (as an int).
        self.colors_spent: Any = 0

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target player (draw) and any target (damage)."""
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

    def _converge_count(self) -> int:
        """X — the number of colors of mana spent to cast this spell."""
        cs = getattr(self, "colors_spent", 0)
        if isinstance(cs, (list, set, tuple)):
            return len(cs)
        return int(cs)

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the converge triple-effect."""
        from engine.game import deal_damage, draw_card

        x = self._converge_count()
        if x <= 0:
            return

        chosen = getattr(self, "chosen_targets", None) or []
        target_player = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None

        if target_player is not None and hasattr(target_player, "life"):
            for _ in range(x):
                draw_card(game, target_player)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
