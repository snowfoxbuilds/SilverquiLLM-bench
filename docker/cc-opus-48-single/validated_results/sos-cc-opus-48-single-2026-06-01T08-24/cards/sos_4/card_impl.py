"""Card implementation for Together as One (SOS 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    """Return ``True`` if *obj* is a creature object."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _is_player(obj: Any) -> bool:
    """Return ``True`` if *obj* is a player (has life, is not a card)."""
    return hasattr(obj, "life") and not getattr(obj, "card_types", None)


def _is_any_target(obj: Any) -> bool:
    """'any target' = any creature, player, planeswalker, or battle.

    The engine models only creatures and players among these, so accept an
    object that is either a creature or a player.
    """
    return _is_creature(obj) or _is_player(obj)


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
        # Converge tracking: colors of mana spent to cast (set during casting).
        self.colors_spent: list = []

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Advertise two targets: a target player and an 'any target'."""
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
        """Resolve Together as One.

        X = number of colors of mana spent (Converge). The target player draws
        X cards, this spell deals X damage to the 'any target', and the
        controller gains X life.
        """
        x = len(getattr(self, "colors_spent", []) or [])
        if x <= 0:
            return

        targets = list(getattr(self, "chosen_targets", []) or [])
        target_player = targets[0] if len(targets) >= 1 else None
        damage_target = targets[1] if len(targets) >= 2 else None

        # Target player draws X cards.
        if target_player is not None and hasattr(target_player, "life"):
            from engine.game import draw_card

            for _ in range(x):
                draw_card(game, target_player)

        # Deal X damage to the 'any target'.
        if damage_target is not None:
            from engine.game import deal_damage

            deal_damage(game, self, damage_target, x)

        # Controller gains X life.
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
