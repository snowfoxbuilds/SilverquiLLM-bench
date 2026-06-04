"""Card implementation for Together as One (SOS #4).

Together as One — ``{6}`` colorless Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.

X is driven by the converge mechanic.  The cast pipeline records the distinct
colors of mana spent to pay the cost on the spell as
``card.colors_spent`` (a list of :class:`~engine.types.Color`, sourced from
:attr:`engine.mana.ManaPool.last_payment_colors`).  ``on_resolve`` reads that
list, computes ``X = len(colors_spent)``, and applies the three clauses in a
single resolution.  When ``X == 0`` (e.g. an all-colorless payment) the spell
is fully inert.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    """Return True if *obj* is a player (has a life total and is not a card)."""
    return hasattr(obj, "life") and not hasattr(obj, "card_types")


def _is_creature(obj: Any) -> bool:
    """Return True if *obj* is a creature object."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery (colorless).

    SOS collector number 4 (converge + multi-target reference slot).
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

    # ------------------------------------------------------------------
    # Targeting — "target player" then "any target", in that order.
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: a player (draws X), then 'any target' (takes X damage)."""
        return [
            TargetRequirement(
                filter_fn=_is_player,
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
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Apply draw + damage + life gain in one resolution.

        X is the number of distinct colors of mana spent to cast this spell.
        With X == 0 every clause is a no-op.
        """
        from engine.game import deal_damage, draw_card

        x = len(getattr(self, "colors_spent", []) or [])
        if x <= 0:
            return

        targets = getattr(self, "chosen_targets", None) or []
        target_player = targets[0] if len(targets) >= 1 else None
        damage_target = targets[1] if len(targets) >= 2 else None

        # Snapshot the controller's life before the damage clause so the
        # "you gain X life" clause adds X relative to that baseline.  This
        # keeps the life-gain clause independent of whichever object is the
        # damage target (including when the controller is the damage target).
        controller = self.controller
        has_life = controller is not None and hasattr(controller, "life")
        pre_life = controller.life if has_life else 0

        # 1. Target player draws X cards.
        if target_player is not None and _is_player(target_player):
            for _ in range(x):
                draw_card(game, target_player)

        # 2. Together as One deals X damage to any target.
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # 3. You (controller) gain X life.
        if has_life:
            controller.life = pre_life + x
