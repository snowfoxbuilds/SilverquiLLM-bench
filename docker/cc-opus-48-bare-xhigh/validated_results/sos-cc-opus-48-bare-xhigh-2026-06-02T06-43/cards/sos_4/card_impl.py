"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _converge_count(card: Any) -> int:
    """Return X for converge — the number of colors of mana spent to cast *card*.

    The real casting pipeline records ``colors_spent`` as a list of
    :class:`~engine.types.Color`; tests (and some reference cards) set it as a
    plain integer.  Support both.
    """
    spent = getattr(card, "colors_spent", 0)
    if isinstance(spent, int):
        return spent
    try:
        return len(set(spent))
    except TypeError:
        return 0


def _is_any_target(obj: Any) -> bool:
    """Return ``True`` if *obj* is a legal "any target" (creature, player, or planeswalker)."""
    if hasattr(obj, "life"):
        return True
    card_types = getattr(obj, "card_types", set())
    if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
        return True
    return False


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
        # Distinct colors of mana spent to cast this spell (set by the casting
        # pipeline as a list; may be overridden as an int by tests).
        self.colors_spent: Any = 0

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Two targets: a player (to draw) and any target (to damage)."""
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

    def on_resolve(self, game: "GameState") -> None:
        """Draw X for the target player, deal X to the damage target, gain X life."""
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import deal_damage, draw_card

        x = _converge_count(self)
        if x <= 0:
            return

        chosen = getattr(self, "chosen_targets", []) or []
        player_target = chosen[0] if len(chosen) >= 1 else None
        damage_target = chosen[1] if len(chosen) >= 2 else None

        if player_target is not None and hasattr(player_target, "life"):
            for _ in range(x):
                draw_card(game, player_target)

        if damage_target is not None:
            deal_damage(game, self, damage_target, x)

        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += x
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=x),
            )
