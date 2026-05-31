"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _make_inkling_token() -> Creature:
    """Create the 1/1 white and black Inkling token used by the ETB ability."""
    return Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
    )


def _count_creatures(game: "GameState", player: "Player") -> int:
    """Count creatures that player currently controls on the battlefield."""
    return sum(
        1
        for permanent in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(permanent, "card_types", set())
    )


def _is_on_battlefield(game: "GameState", permanent: Any) -> bool:
    """Return whether the given permanent is on any battlefield."""
    return any(
        game.get_battlefield(player).contains(permanent)
        for player in game.players
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    # UNVERIFIED: While it's prepared, you may cast a copy of its spell. Doing so unprepares it. — card spec omits spell-face oracle text and engine has no public prepared-spell casting API
    # UNVERIFIED: {1}{W}{W} // {W} and Creature — Cat Cleric // Instant — no public multi-face metadata convention exists in the repository

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        from engine.game import create_token

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(
            game: "GameState",
            event: EntersBattlefieldTriggeredEvent,
        ) -> bool:
            return event.permanent is source

        def _get_targets(
            game: "GameState",
            event: EntersBattlefieldTriggeredEvent,
        ) -> list[Any]:
            return list(game.players)

        def _effect(
            game: "GameState",
            *,
            targets: list[Any] | None = None,
            **_: Any,
        ) -> None:
            target_player = targets[0] if targets else None
            if target_player is None:
                return

            create_token(game, target_player, _make_inkling_token())

            current_controller = getattr(source, "controller", None)
            if current_controller is None or not _is_on_battlefield(game, source):
                return

            your_creature_count = _count_creatures(game, current_controller)
            if any(
                opponent is not current_controller
                and _count_creatures(game, opponent) > your_creature_count
                for opponent in game.players
            ):
                source.is_prepared = True

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                get_targets=_get_targets,
                target_description="target player",
            )
        )
