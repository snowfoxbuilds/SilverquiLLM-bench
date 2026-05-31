"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    Prepared — While it's prepared, you may cast a copy of its spell
    (Swords to Plowshares: exile target creature, its controller gains
    life equal to its power). Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        # Prepared keyword state
        self.is_prepared: bool = False

    def _count_creatures_on_battlefield(self, game: "GameState", player: Any) -> int:
        """Count creature permanents a player controls on the battlefield."""
        bf = game.get_battlefield(player)
        return sum(
            1 for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )

    def on_resolve(self, game: "GameState") -> None:
        """ETB: create Inkling token for target player, then check preparation."""
        from engine.game import create_token

        targets = getattr(self, "chosen_targets", None) or []
        target_player = targets[0] if targets else self.controller
        if target_player is None:
            return

        # Create 1/1 white/black Inkling with flying for target player.
        inkling = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, target_player, inkling)

        # Check if an opponent controls more creatures than this card's controller.
        controller = self.controller
        if controller is None:
            return
        my_count = self._count_creatures_on_battlefield(game, controller)
        for player in game.players:
            if player is not controller:
                their_count = self._count_creatures_on_battlefield(game, player)
                if their_count > my_count:
                    self.is_prepared = True
                    return

    def cast_prepared_spell(self, game: "GameState", target: Any) -> None:
        """Cast a copy of Swords to Plowshares from the prepared state.

        Exiles the target creature and gives its controller life equal to
        the target's power. Unprepares this creature afterward.

        Parameters:
            game: Current game state.
            target: The creature to exile (must be on the battlefield).
        """
        if not self.is_prepared:
            return

        from engine.game import exile

        # Exile the target creature and its controller gains life = power.
        power = getattr(target, "base_power", 0)
        target_controller = getattr(target, "controller", None)

        exile(game, target)

        if target_controller is not None and hasattr(target_controller, "life"):
            target_controller.life += power

        # Unprepare.
        self.is_prepared = False
