"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    """Return ``True`` if *obj* is a player (the only object with ``life``)."""
    return hasattr(obj, "life")


def _is_creature(obj: Any) -> bool:
    """Return ``True`` if *obj* is a creature object."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.

    X is read from ``self.colors_spent`` — the list of distinct
    :class:`~engine.types.Color` values the cast pipeline records from the
    payer's ``mana_pool.last_payment_colors`` (colorless excluded, already
    de-duplicated).  ``X == len(self.colors_spent)``.

    SOS collector number 4.
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
        # Distinct colors of mana spent to cast this spell. The cast pipeline
        # overwrites this with a list of Color values; default to an empty
        # list so X == 0 before any payment (a no-op for every clause).
        self.colors_spent: list[Any] = []

    # ------------------------------------------------------------------
    # Targeting — a target player (draw) and an any-target (damage).
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two requirements: (1) target player, (2) any target."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: _is_player(obj),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: _is_player(obj) or _is_creature(obj),
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    # ------------------------------------------------------------------
    # Resolution — draw X / deal X damage / gain X life.
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Apply all three Converge clauses scaled by X (distinct colors spent)."""
        from engine.game import deal_damage, draw_card

        x = len(getattr(self, "colors_spent", []) or [])
        if x <= 0:
            return

        chosen = getattr(self, "chosen_targets", None) or []
        target_player = chosen[0] if len(chosen) >= 1 else None
        damage_target = chosen[1] if len(chosen) >= 2 else None

        # 1. Target player draws X cards.
        if target_player is not None and _is_player(target_player):
            for _ in range(x):
                draw_card(game, target_player)

        # 2. Together as One deals X damage to the any-target.
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # 3. You (the controller) gain X life.
        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
