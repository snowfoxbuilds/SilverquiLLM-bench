"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.game import create_token
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
        return event.permanent is source

    return _condition


def _count_creatures(game: "GameState", player: "Player") -> int:
    """Return the number of creatures *player* controls on the battlefield."""
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _is_on_battlefield(game: "GameState", permanent: Any) -> bool:
    """Return whether *permanent* is currently on any battlefield."""
    return any(game.get_battlefield(player).contains(permanent) for player in game.players)


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

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
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self.colors = {Color.WHITE}
        self.is_prepared: bool = False

    def _make_inkling_token(self, controller: "Player") -> Creature:
        """Create the Inkling token object used by the ETB trigger."""
        token = Creature(
            name="Inkling",
            owner=controller,
            controller=controller,
            subtypes={"Inkling"},
            base_power=1,
            base_toughness=1,
            keywords=Keyword.FLYING,
        )
        token.colors = {Color.WHITE, Color.BLACK}
        return token

    def _update_prepared_state(self, game: "GameState", reference_controller: "Player") -> None:
        """Prepare this creature if any opponent controls more creatures."""
        your_creatures = _count_creatures(game, reference_controller)
        self.is_prepared = any(
            opponent is not reference_controller and _count_creatures(game, opponent) > your_creatures
            for opponent in game.players
        )

    # UNVERIFIED: prepared-copy cast behavior and unprepare-on-cast are only partially implemented because the spec does not define the copied spell-side effect.
    def cast_prepared_copy(self, game: "GameState") -> None:
        """Placeholder for the untested prepared-copy behavior."""
        return

    def _make_enter_trigger_effect(
        self, game: "GameState", trigger_controller: "Player" | None
    ):
        """Create the ETB trigger's resolution callback with locked-in choices."""
        if trigger_controller is None:
            return lambda _game: None

        legal_targets = list(game.players)
        chosen = (
            trigger_controller.choose_target(legal_targets, "player")
            if hasattr(trigger_controller, "choose_target")
            else (legal_targets[0] if legal_targets else None)
        )
        if chosen not in legal_targets:
            return lambda _game: None

        def _resolve(game: "GameState") -> None:
            create_token(game, chosen, self._make_inkling_token(chosen))
            if _is_on_battlefield(game, self):
                self._update_prepared_state(game, trigger_controller)

        return _resolve

    def register_triggers(self, game: "GameState") -> None:
        """Register the enters-the-battlefield trigger."""
        source = self
        trigger_controller = self.controller or game.active_player

        def _effect_factory(
            game: "GameState", event: EntersBattlefieldTriggeredEvent
        ):
            if trigger_controller is None or event.permanent is not source:
                return lambda _game: None
            return source._make_enter_trigger_effect(game, trigger_controller)

        def _effect(game: "GameState") -> None:
            return

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition(self),
                effect=_effect,
                source=self,
                controller=trigger_controller,
                effect_factory=_effect_factory,
            )
        )

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Handle the self-enter trigger for normal battlefield entry paths."""
        trigger_controller = self.controller or game.active_player
        game.stack.push(
            StackObject(
                source=self,
                controller=trigger_controller,
                on_resolve=self._make_enter_trigger_effect(game, trigger_controller),
            )
        )
