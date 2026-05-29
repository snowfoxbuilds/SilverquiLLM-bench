"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.game import create_token
from engine.types import Color, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares.

    Only the tested creature-face behaviour is implemented here. The prepared
    spell-copy clause remains intentionally unimplemented per RUN_DECISIONS.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self.colors = {Color.WHITE}
        self.is_prepared = False

    def on_resolve(self, game: "GameState") -> None:
        """Apply the tested ETB effect without inventing spell-face behaviour.

        The engine currently does not let a permanent register a self-ETB trigger
        in time to see its own entry, so the ETB effect is executed during spell
        resolution before the permanent moves onto the battlefield. For the
        current tests, this preserves the required token creation and post-token
        creature-count preparation check.
        """
        controller = self.controller
        if controller is None:
            return

        target_player = self._choose_target_player(game, controller)
        if target_player is None:
            return

        inkling = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        inkling.colors = {Color.WHITE, Color.BLACK}
        create_token(game, target_player, inkling)

        self.is_prepared = self._opponent_controls_more_creatures_than_you(
            game,
            controller,
        )

    def _choose_target_player(
        self,
        game: "GameState",
        controller: "Player",
    ) -> "Player | None":
        players = list(game.players)
        try:
            chosen = controller.choose_target(players, "target player")
        except Exception:
            chosen = controller.choose_card(players, "target player")
        return chosen if chosen in players else None

    def _opponent_controls_more_creatures_than_you(
        self,
        game: "GameState",
        controller: "Player",
    ) -> bool:
        your_count = self._count_creatures_you_control(game, controller) + 1
        return any(
            self._count_creatures_you_control(game, player) > your_count
            for player in game.players
            if player is not controller
        )

    @staticmethod
    def _count_creatures_you_control(game: "GameState", player: "Player") -> int:
        battlefield = game.get_battlefield(player)
        return sum(
            1
            for permanent in battlefield.get_all()
            if getattr(permanent, "card_types", None)
            and any(card_type.value == "creature" for card_type in permanent.card_types)
        )
