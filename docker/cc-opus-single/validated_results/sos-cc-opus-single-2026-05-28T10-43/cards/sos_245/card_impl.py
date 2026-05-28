"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_creatures(game: "GameState", player: Any) -> int:
    """Count the number of creatures a player controls on the battlefield."""
    bf = game.get_battlefield(player)
    count = 0
    for obj in bf.get_all():
        card_types = getattr(obj, "card_types", set())
        if CardType.CREATURE in card_types:
            count += 1
    return count


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer -- {6}{B}{G} -- 5/5 Elder Dragon.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword(0))
        kwargs["keywords"] = kwargs["keywords"] | Keyword.FLYING | Keyword.DEATHTOUCH
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Self affinity -- Affinity for creatures
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return the number of creatures the controller controls.

        Affinity for creatures: this spell costs {1} less to cast for
        each creature you control. Returns the raw count; the engine's
        get_cost_reduction() clamps to generic cost.
        """
        player = self.controller or self.owner
        if player is None:
            return 0
        return _count_creatures(game, player)

    # ------------------------------------------------------------------
    # Grants affinity to instant and sorcery spells
    # ------------------------------------------------------------------

    def _affinity_grant(self, game: "GameState", card: Any) -> int:
        """Cost reduction grant for instants/sorceries cast by controller.

        Returns the number of creatures the controller controls, but only
        if the card is an instant or sorcery controlled by the same player
        who controls Witherbloom.
        """
        # Only grant affinity to instants and sorceries
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return 0
        # Only grant to spells controlled by our controller
        card_controller = getattr(card, "controller", None)
        our_controller = self.controller or self.owner
        if card_controller is None or our_controller is None:
            return 0
        if card_controller is not our_controller:
            return 0
        return _count_creatures(game, our_controller)

    def register_triggers(self, game: "GameState") -> None:
        """Register the affinity-granting effect for instants/sorceries.

        Adds a cost reduction grant to the game state so that instants
        and sorceries cast by the controller get affinity for creatures.
        """
        # Store reference to the grant function for later unregistration
        self._affinity_grant_fn = lambda g, c: self._affinity_grant(g, c)

        # Register the cost reduction grant on the game state
        grants = getattr(game, "_cost_reduction_grants", None)
        if grants is None:
            game._cost_reduction_grants = []
            grants = game._cost_reduction_grants
        grants.append(self._affinity_grant_fn)

    def _unregister_grants(self, game: "GameState") -> None:
        """Remove the affinity grant when Witherbloom leaves the battlefield."""
        grant_fn = getattr(self, "_affinity_grant_fn", None)
        if grant_fn is None:
            return
        grants = getattr(game, "_cost_reduction_grants", None)
        if grants is not None and grant_fn in grants:
            grants.remove(grant_fn)
