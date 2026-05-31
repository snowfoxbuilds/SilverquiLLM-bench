"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_controller_battlefield(game: "GameState", permanent: Any) -> bool:
    controller = getattr(permanent, "controller", None)
    if controller is None:
        return False
    return controller.zones[Zone.BATTLEFIELD].contains(permanent)


def _count_creatures_you_control(game: "GameState", controller: Any) -> int:
    if controller is None:
        return 0
    return sum(
        1
        for permanent in game.get_battlefield(controller).get_all()
        if CardType.CREATURE in getattr(permanent, "card_types", set())
    )


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        return _count_creatures_you_control(game, self.controller)

    def get_granted_cost_reduction(
        self,
        game: "GameState",
        player: Any,
        card: Any,
    ) -> int | None:
        if player is not self.controller:
            return None
        if not _is_on_controller_battlefield(game, self):
            return None

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None

        return _count_creatures_you_control(game, player)
