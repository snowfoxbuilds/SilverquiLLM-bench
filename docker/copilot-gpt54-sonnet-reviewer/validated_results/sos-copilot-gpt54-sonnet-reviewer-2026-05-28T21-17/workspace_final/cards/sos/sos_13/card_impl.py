"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.game import create_token
from engine.triggers import TriggerRegistration
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


if not hasattr(Keyword, "PREPARED"):
    Keyword.PREPARED = Keyword(max(keyword.value for keyword in Keyword) << 1)  # type: ignore[attr-defined]


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Creature half implementation for Emeritus of Truce // Swords to Plowshares."""

    def __init__(self, **kwargs: Any) -> None:
        keywords = kwargs.pop("keywords", Keyword(0)) | Keyword.PREPARED
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", keywords)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black Inkling "
            "creature token with flying. Then if an opponent controls more creatures than you, "
            "this creature becomes prepared.",
        )
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.colors = ["W"]
        self.keywords |= Keyword.PREPARED
        self._original_keywords = self.keywords
        self.is_prepared = False
        # UNVERIFIED: Prepared spell-copy casting is intentionally omitted; the engine has no
        # UNVERIFIED: documented prepared-copy casting API and the spec provides no canonical spell-half rules text.
        # UNVERIFIED: Spell-half metadata is intentionally omitted; the project has no established
        # UNVERIFIED: public schema for representing the second face on a creature implementation.

    def on_resolve(self, game: "GameState") -> None:
        """Mirror the ETB effect during spell resolution because self-ETB triggers do not self-fire in this engine."""
        self._create_inkling_and_update_prepared(game)

    def register_triggers(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        def _condition(_game: "GameState", event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is self

        def _effect(resolving_game: "GameState") -> None:
            self._create_inkling_and_update_prepared(resolving_game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _create_inkling_and_update_prepared(self, game: "GameState") -> None:
        source_controller = self.controller
        if source_controller is None:
            return

        chosen_player = source_controller.choose_target(game.players, "target player")
        if chosen_player is None:
            return

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        token.colors = ["W", "B"]
        create_token(game, chosen_player, token)

        your_creature_count = self._count_creatures(game, source_controller)
        self.is_prepared = any(
            opponent is not source_controller and self._count_creatures(game, opponent) > your_creature_count
            for opponent in game.players
        )

    @staticmethod
    def _count_creatures(game: "GameState", player: Any) -> int:
        return sum(
            1
            for permanent in game.get_battlefield(player).get_all()
            if isinstance(permanent, Creature)
        )
