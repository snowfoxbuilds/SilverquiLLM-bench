"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _count_creatures(game: GameState, controller: Player) -> int:
    """Count the number of creatures *controller* controls on the battlefield."""
    count = 0
    for obj in game.get_battlefield(controller).get_all():
        card_types = getattr(obj, "card_types", set())
        if CardType.CREATURE in card_types:
            count += 1
    return count


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer -- {6}{B}{G} -- 5/5 -- Legendary Elder Dragon.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.
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
            "each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: GameState) -> int:
        """Affinity for creatures -- reduce cost by the number of creatures
        the controller controls on the battlefield."""
        controller = self.controller
        if controller is None:
            return 0
        return _count_creatures(game, controller)

    def register_triggers(self, game: GameState) -> None:
        """Register the external cost-reduction provider that grants affinity
        for creatures to the controller's instant and sorcery spells."""
        source = self

        def _affinity_provider(
            game: GameState, card: Any, controller: Player
        ) -> int:
            """Return the creature-count reduction for *card* if it qualifies.

            Only applies if:
            - The spell is an instant or sorcery.
            - The controller of the spell is the same player who controls
              Witherbloom.
            """
            # Only grant to instants and sorceries
            card_types = getattr(card, "card_types", set())
            if not (CardType.INSTANT in card_types or CardType.SORCERY in card_types):
                return 0
            # Only grant to spells cast by Witherbloom's controller
            if controller is not source.controller:
                return 0
            return _count_creatures(game, controller)

        # Register the provider on the game state
        if not hasattr(game, "_cost_reduction_providers"):
            game._cost_reduction_providers = []
        game._cost_reduction_providers.append({
            "source": source,
            "provider": _affinity_provider,
        })
