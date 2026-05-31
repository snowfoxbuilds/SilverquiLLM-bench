"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.casting import CastingError, cast_spell_from_zone
from engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class PreparedSwordsToPlowshares(Instant):
    """The prepared spell copy associated with Emeritus of Truce."""

    def __init__(self, source_permanent: "EmeritusOfTruceSwordsToPlowshares", **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)
        self.colors = {Color.WHITE}
        self.prepared_source = source_permanent
        self.is_spell_copy = True

    def can_cast(self, game: "GameState") -> bool:
        source = getattr(self, "prepared_source", None)
        controller = getattr(source, "controller", None)
        if source is None or controller is None:
            return False
        if not getattr(source, "is_prepared", False):
            return False
        if not controller.zones[Zone.BATTLEFIELD].contains(source):
            return False
        owner = getattr(self, "owner", None)
        if owner is None:
            return False
        return owner.zones[Zone.EXILE].contains(self)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        def _is_creature_on_battlefield(target: Any) -> bool:
            if target is None:
                return False
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return False
            return any(player.zones[Zone.BATTLEFIELD].contains(target) for player in game.players)

        return [
            TargetRequirement(
                filter_fn=_is_creature_on_battlefield,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        controller = None
        for player in game.players:
            if player.zones[Zone.BATTLEFIELD].contains(target):
                controller = getattr(target, "controller", None) or player
                break
        if controller is None:
            return

        power = getattr(target, "power", getattr(target, "base_power", 0))
        exile(game, target)
        controller.life += max(0, power)
        game.trigger_manager.fire_event(
            game,
            GainsLifeTriggeredEvent(player=controller, amount=max(0, power)),
        )


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
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.colors = {Color.WHITE}
        self.is_prepared = False
        self.prepared = False
        self._prepared_spell_copy: PreparedSwordsToPlowshares | None = None

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _effect(game: "GameState") -> None:
            source._handle_enter_trigger(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _handle_enter_trigger(self, game: "GameState") -> None:
        target_player = self._get_target_player(game)
        if target_player is None:
            return

        self._create_inkling_token(game, target_player)
        if self._opponent_controls_more_creatures(game):
            self.become_prepared(game)

    def _get_target_player(self, game: "GameState") -> "Player | None":
        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        return target if target in game.players else None

    def _create_inkling_token(self, game: "GameState", target_player: "Player") -> None:
        from engine.game import create_token

        token = Creature(
            name="Inkling",
            owner=target_player,
            controller=target_player,
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        token.colors = {Color.WHITE, Color.BLACK}
        create_token(game, target_player, token)

    def _opponent_controls_more_creatures(self, game: "GameState") -> bool:
        controller = self.controller
        if controller is None:
            return False
        your_creatures = self._count_creatures(game, controller)
        for player in game.players:
            if player is controller:
                continue
            if self._count_creatures(game, player) > your_creatures:
                return True
        return False

    def _count_creatures(self, game: "GameState", player: "Player") -> int:
        return sum(
            1
            for obj in game.get_battlefield(player).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def become_prepared(self, game: "GameState") -> None:
        if getattr(self, "is_prepared", False):
            return
        self.is_prepared = True
        self.prepared = True
        self._create_prepared_spell_copy()

    def become_unprepared(self, game: "GameState") -> None:
        self.is_prepared = False
        self.prepared = False
        self._remove_prepared_spell_copy()

    def _create_prepared_spell_copy(self) -> PreparedSwordsToPlowshares | None:
        controller = getattr(self, "controller", None)
        if controller is None:
            return None
        self._remove_prepared_spell_copy()
        prepared_copy = PreparedSwordsToPlowshares(
            source_permanent=self,
            owner=controller,
            controller=controller,
        )
        controller.zones[Zone.EXILE].add(prepared_copy)
        self._prepared_spell_copy = prepared_copy
        return prepared_copy

    def _remove_prepared_spell_copy(self) -> None:
        prepared_copy = getattr(self, "_prepared_spell_copy", None)
        if prepared_copy is None:
            return
        owner = getattr(prepared_copy, "owner", None)
        if owner is not None and owner.zones[Zone.EXILE].contains(prepared_copy):
            owner.zones[Zone.EXILE].remove(prepared_copy)
        self._prepared_spell_copy = None

    def get_prepared_spell_copy(self) -> PreparedSwordsToPlowshares | None:
        prepared_copy = getattr(self, "_prepared_spell_copy", None)
        if prepared_copy is None:
            return None
        owner = getattr(prepared_copy, "owner", None)
        if owner is None or not owner.zones[Zone.EXILE].contains(prepared_copy):
            return None
        if not getattr(self, "is_prepared", False):
            return None
        return prepared_copy

    def can_cast_prepared_copy(self, game: "GameState") -> bool:
        prepared_copy = self.get_prepared_spell_copy()
        return prepared_copy is not None and prepared_copy.can_cast(game)

    def cast_prepared_copy(self, game: "GameState") -> None:
        controller = getattr(self, "controller", None)
        prepared_copy = self.get_prepared_spell_copy()
        if controller is None or prepared_copy is None:
            raise CastingError(f"Cannot cast prepared copy for {self.name!r}")
        cast_spell_from_zone(game, controller, prepared_copy, Zone.EXILE)
        self.become_unprepared(game)
