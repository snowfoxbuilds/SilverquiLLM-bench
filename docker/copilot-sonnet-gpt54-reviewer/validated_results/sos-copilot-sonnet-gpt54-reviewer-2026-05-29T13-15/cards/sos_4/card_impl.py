"""Card implementation for Together as One (sos_4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


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
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)
        # Set by the casting engine (list of Color) or directly in tests (int).
        self.colors_spent: Any = 0

    def _get_x(self) -> int:
        """Return X = number of distinct colors of mana spent."""
        val = getattr(self, "colors_spent", 0)
        if isinstance(val, list):
            return len(val)
        return int(val)

    def on_resolve(self, game: "GameState") -> None:
        """Draw X, deal X, gain X based on colors spent."""
        x = self._get_x()
        if x == 0:
            return

        chosen = getattr(self, "chosen_targets", [])
        target_player = chosen[0] if len(chosen) > 0 else None
        damage_target = chosen[1] if len(chosen) > 1 else None

        # Draw X cards for target player
        if target_player is not None and hasattr(target_player, "zones"):
            library = target_player.zones
            from engine.types import Zone
            lib = target_player.zones[Zone.LIBRARY]
            hand = target_player.zones[Zone.HAND]
            for _ in range(x):
                top = lib.top(1)
                if top:
                    card = top[0]
                    lib.remove(card)
                    hand.add(card)

        # Deal X damage to any target
        if damage_target is not None:
            if hasattr(damage_target, "damage_marked"):
                # Creature or planeswalker
                damage_target.damage_marked = getattr(damage_target, "damage_marked", 0) + x
            elif hasattr(damage_target, "life"):
                # Player
                damage_target.life -= x
            elif hasattr(damage_target, "loyalty"):
                # Planeswalker
                damage_target.loyalty -= x

        # Gain X life for controller
        controller = self.controller
        if controller is not None:
            controller.life += x
