"""Card implementation for Together as One (SOS 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    """Return ``True`` if *obj* is a player (has a ``life`` total)."""
    return hasattr(obj, "life")


def _is_creature(obj: Any) -> bool:
    """Return ``True`` if *obj* is a creature card/permanent."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _is_any_target(obj: Any) -> bool:
    """Return ``True`` if *obj* is a legal "any target".

    "Any target" means a player, planeswalker, battle, or creature — not a
    plain non-creature permanent such as a land.
    """
    if _is_player(obj):
        return True
    card_types = getattr(obj, "card_types", set())
    return bool(card_types & {CardType.CREATURE, CardType.PLANESWALKER})


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
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Colors of mana spent to cast this spell, recorded during payment
        # (see engine.casting / engine.mana last_payment_colors). Set by the
        # cast pipeline or directly by tests. X is the number of DISTINCT
        # colors in this list.
        self.colors_spent: list[Any] = []

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target player (draw) and an "any target" (damage)."""
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

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Converge resolution: draw X, deal X damage, gain X life."""
        from engine.game import deal_damage, draw_card

        colors = getattr(self, "colors_spent", None) or []
        x = len(set(colors))
        if x <= 0:
            return

        targets = getattr(self, "chosen_targets", None) or []
        player_target = targets[0] if len(targets) >= 1 else None
        damage_target = targets[1] if len(targets) >= 2 else None

        # Target player draws X cards.
        if player_target is not None and _is_player(player_target):
            for _ in range(x):
                draw_card(game, player_target)

        # Together as One deals X damage to any target.
        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        # You gain X life (the controller — not targeted).
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
