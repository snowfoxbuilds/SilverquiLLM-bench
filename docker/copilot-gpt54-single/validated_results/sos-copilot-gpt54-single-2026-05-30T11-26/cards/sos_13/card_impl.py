"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _count_creatures(game: "GameState", player: "Player") -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _is_on_battlefield(game: "GameState", obj: object) -> bool:
    return any(game.get_battlefield(player).contains(obj) for player in game.players)


class SwordsToPlowsharesPreparedCopy(Instant):
    """Prepared spell-side copy for Emeritus of Truce."""

    def __init__(
        self,
        *,
        prepared_source: "EmeritusOfTruceSwordsToPlowshares | None" = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("rules_text", "Prepared spell copy.")
        super().__init__(**kwargs)
        self.prepared_source = prepared_source
        self.set_base_colors({Color.WHITE})

    def on_cast(self, game: "GameState") -> None:
        source = self.prepared_source
        if source is not None:
            source.unprepare()

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile
        from engine.protection import has_protection_from

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return
        if has_protection_from(target, self):
            return

        gained_life = getattr(target, "power", getattr(target, "base_power", 0))
        target_controller = getattr(target, "controller", None) or getattr(target, "owner", None)
        exile(game, target)
        if target_controller is not None and gained_life > 0:
            target_controller.life += gained_life
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=target_controller, amount=gained_life),
            )

    def choose_default_target(self, game: "GameState") -> object | None:
        preferred_exclusions = {self.prepared_source}
        fallback_target = None
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE not in getattr(obj, "card_types", set()):
                    continue
                if fallback_target is None:
                    fallback_target = obj
                if obj not in preferred_exclusions:
                    return obj
        return fallback_target


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
        self.set_base_colors({Color.WHITE})
        self.is_prepared: bool = False
        self.prepared_copy: SwordsToPlowsharesPreparedCopy | None = None

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = self.controller or game.active_player

        def _condition(game: "GameState", event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _effect(game: "GameState") -> None:
            return

        def _stack_factory(
            game: "GameState",
            event: EntersBattlefieldTriggeredEvent,
            trigger: TriggerRegistration,
        ) -> StackObject:
            ctrl = source.controller
            if ctrl is None:
                return StackObject(source=source, controller=trigger.controller, on_resolve=lambda g: None)

            try:
                chosen_player = ctrl.choose(list(game.players), "Choose a player to create an Inkling")
            except Exception:
                chosen_player = ctrl
            if chosen_player not in game.players:
                chosen_player = None

            def _resolve_selected_trigger(resolving_game: "GameState") -> None:
                source._resolve_enters_ability(resolving_game, chosen_player)

            return StackObject(
                source=source,
                controller=ctrl,
                targets=[] if chosen_player is None else [chosen_player],
                on_resolve=_resolve_selected_trigger,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                stack_factory=_stack_factory,
                source=self,
                controller=controller,
            )
        )

    def _resolve_enters_ability(self, game: "GameState", target_player: "Player | None") -> None:
        from engine.game import create_token

        if target_player is not None:
            inkling = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            inkling.set_base_colors({Color.WHITE, Color.BLACK})
            create_token(game, target_player, inkling)

        controller = self.controller
        if controller is None:
            return

        your_creature_count = _count_creatures(game, controller)
        if any(
            _count_creatures(game, player) > your_creature_count
            for player in game.players
            if player is not controller
        ):
            self.prepare(game)

    def prepare(self, game: "GameState") -> SwordsToPlowsharesPreparedCopy | None:
        controller = self.controller or self.owner
        if controller is None:
            return None
        if self.is_prepared:
            return self.get_prepared_copy(game)

        prepared_copy = SwordsToPlowsharesPreparedCopy(
            owner=controller,
            controller=controller,
            prepared_source=self,
        )
        game.get_exile(controller).add(prepared_copy)
        self.is_prepared = True
        self.prepared_copy = prepared_copy
        return prepared_copy

    def unprepare(self) -> None:
        self.is_prepared = False
        if self.prepared_copy is not None:
            self.prepared_copy.prepared_source = None
        self.prepared_copy = None

    def _find_prepared_copy(
        self,
        game: "GameState",
    ) -> tuple["Player | None", SwordsToPlowsharesPreparedCopy | None]:
        if self.prepared_copy is not None:
            for player in game.players:
                if game.get_exile(player).contains(self.prepared_copy):
                    return player, self.prepared_copy
        for player in game.players:
            for obj in game.get_exile(player).get_all():
                if isinstance(obj, SwordsToPlowsharesPreparedCopy) and obj.prepared_source is self:
                    self.prepared_copy = obj
                    return player, obj
        return None, None

    def _sync_prepared_copy_controller(
        self,
        game: "GameState",
        current_zone_player: "Player | None",
        prepared_copy: SwordsToPlowsharesPreparedCopy,
    ) -> SwordsToPlowsharesPreparedCopy:
        controller = self.controller or self.owner
        if controller is None:
            return prepared_copy
        prepared_copy.controller = controller
        prepared_copy.owner = controller
        if current_zone_player is not None and current_zone_player is not controller:
            game.get_exile(current_zone_player).remove(prepared_copy)
            game.get_exile(controller).add(prepared_copy)
        return prepared_copy

    def get_prepared_copy(self, game: "GameState") -> SwordsToPlowsharesPreparedCopy | None:
        current_zone_player, prepared_copy = self._find_prepared_copy(game)
        if prepared_copy is None:
            return None
        return self._sync_prepared_copy_controller(game, current_zone_player, prepared_copy)

    def cast_prepared_copy(self, game: "GameState") -> None:
        from engine.casting import cast_spell_from_zone

        controller = self.controller or self.owner
        if controller is None:
            raise ValueError("Prepared copy has no controller")

        prepared_copy = self.get_prepared_copy(game)
        if prepared_copy is None:
            raise ValueError("This permanent has no prepared spell copy to cast")

        if (
            hasattr(controller, "remaining_choices")
            and getattr(controller, "remaining_choices") == 0
            and hasattr(controller, "_script")
        ):
            default_target = prepared_copy.choose_default_target(game)
            if default_target is not None:
                controller._script.appendleft(default_target)

        cast_spell_from_zone(game, controller, prepared_copy, Zone.EXILE)
