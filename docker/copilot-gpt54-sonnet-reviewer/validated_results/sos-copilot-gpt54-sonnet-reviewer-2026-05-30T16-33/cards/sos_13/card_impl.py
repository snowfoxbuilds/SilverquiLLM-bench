"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _self_etb_condition(source: Any):
    """Return a condition that matches only this permanent entering."""

    def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
        return event.permanent is source

    return _condition


def _count_creatures(game: GameState, player: Player | None) -> int:
    """Count creatures that *player* controls on the battlefield."""
    if player is None:
        return 0
    return sum(
        1
        for permanent in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(permanent, "card_types", set())
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    # UNVERIFIED: (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.) — card_spec.json omits the spell-face oracle text, so the copied spell's authoritative cast/effect contract is unavailable in this workspace.

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
        self.is_prepared = False
        self.prepared_copy: Instant | None = None

    def _get_target_player(self) -> Player | None:
        chosen_targets = getattr(self, "chosen_targets", None)
        if chosen_targets:
            return chosen_targets[0]
        controller = self.controller
        if controller is not None and hasattr(controller, "choose"):
            return controller.choose([], "Choose target player")
        return None

    @staticmethod
    def _create_inkling_token(controller: Player) -> Creature:
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            base_power=1,
            base_toughness=1,
            keywords=Keyword.FLYING,
            owner=controller,
            controller=controller,
        )
        token.colors = {Color.WHITE, Color.BLACK}
        return token

    def _create_prepared_spell_copy(self) -> Instant:
        spell_copy = Instant(
            name="Swords to Plowshares",
            mana_cost=ManaCost.parse("{W}"),
            owner=self.owner,
            controller=self.controller,
        )
        spell_copy.colors = {Color.WHITE}
        return spell_copy

    def register_triggers(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller or self.owner or game.active_player
        source = self

        def _effect(game: GameState) -> None:
            target_player = source._get_target_player()
            source.is_prepared = False
            source.prepared_copy = None

            if target_player is not None:
                create_token(game, target_player, source._create_inkling_token(target_player))

            controller_creatures = _count_creatures(game, controller)
            opponents_ahead = any(
                _count_creatures(game, player) > controller_creatures
                for player in game.players
                if player is not controller
            )
            if not opponents_ahead:
                return

            prepared_copy = source._create_prepared_spell_copy()
            game.get_exile(controller).add(prepared_copy)
            source.is_prepared = True
            source.prepared_copy = prepared_copy

        game.trigger_manager.unregister(self)
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition(self),
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
