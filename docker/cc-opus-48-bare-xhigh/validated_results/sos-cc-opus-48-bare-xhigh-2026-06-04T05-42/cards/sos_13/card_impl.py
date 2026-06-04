"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _creature_count(game: "GameState", player: "Player") -> int:
    if player is None:
        return 0
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    Back face — Swords to Plowshares — {W} — Instant:
    Exile target creature. Its controller gains life equal to its power.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared.",
        )
        super().__init__(**kwargs)
        self.colors = ["W"]
        self.is_prepared: bool = False

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player (creates the Inkling token)",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Own-ETB: create an Inkling for the target player, then maybe prepare."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        targets = getattr(self, "chosen_targets", []) or []
        target_player = targets[0] if targets else controller
        if not _is_player(target_player):
            target_player = controller

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            base_power=1,
            base_toughness=1,
            keywords=Keyword.FLYING,
        )
        token.colors = ["W", "B"]
        create_token(game, target_player, token)

        # Emeritus itself is still on the stack here, so add 1 to account for
        # it entering the battlefield (it counts toward "you").
        my_creatures = _creature_count(game, controller) + 1
        opponents = [p for p in game.players if p is not controller]
        if any(_creature_count(game, opp) > my_creatures for opp in opponents):
            self.is_prepared = True

    def cast_prepared(self, game: "GameState", target_creature: Any) -> bool:
        """Cast the back face (Swords to Plowshares) while prepared.

        Pays {W}, exiles *target_creature*, its controller gains life equal
        to the creature's power, and unprepares this card.  Returns ``True``
        if the spell was cast.
        """
        from engine.game import exile

        if not self.is_prepared:
            return False
        controller = self.controller
        if controller is None or target_creature is None:
            return False
        cost = ManaCost.parse("{W}")
        if not controller.mana_pool.can_pay(cost):
            return False
        controller.mana_pool.pay(cost)

        victim_controller = getattr(target_creature, "controller", None)
        power = getattr(target_creature, "power", 0)
        exile(game, target_creature)
        if victim_controller is not None and hasattr(victim_controller, "life"):
            victim_controller.life += power
        self.is_prepared = False
        return True
