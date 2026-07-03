"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creatures_you_control(game: "GameState", controller: Any) -> int:
    """Number of creatures on *controller*'s battlefield."""
    if controller is None:
        return 0
    return sum(
        1
        for c in game.get_battlefield(controller).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Elder Dragon.

    Affinity for creatures (this spell costs {1} less to cast for each creature
    you control).
    Flying, deathtouch.
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\nFlying, deathtouch\nInstant and "
            "sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Own affinity for creatures: {1} less per creature you control.

        While Witherbloom is being cast it is on the stack, not the
        battlefield, so this naturally counts only your *other* creatures."""
        return _creatures_you_control(game, self.controller)

    def spell_cost_reduction(self, game: "GameState", spell: Any) -> int:
        """Grant affinity for creatures to your instant/sorcery spells.

        E3's battlefield aggregation already gates to instant/sorcery spells
        the controller casts; this returns the creature count to subtract."""
        if CardType.INSTANT not in getattr(spell, "card_types", set()) and (
            CardType.SORCERY not in getattr(spell, "card_types", set())
        ):
            return 0
        return _creatures_you_control(game, self.controller)
