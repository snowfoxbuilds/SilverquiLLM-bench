"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _count_creatures(game: "GameState", player: "Player") -> int:
    """Return the number of creatures *player* controls on the battlefield."""
    return sum(1 for obj in game.get_battlefield(player).get_all() if isinstance(obj, Creature))


def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
        return event.permanent is source

    return _condition


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    # UNVERIFIED: While it's prepared, you may cast a copy of its spell. Doing so unprepares it. — The current spec omits the spell-side rules text and the engine has no public prepared-action API.

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black Inkling creature token with flying. "
            "Then if an opponent controls more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _choose_targets(
            game: "GameState",
            event: EntersBattlefieldTriggeredEvent,
            player: Any,
        ) -> list[Any] | None:
            legal_targets = list(game.players)
            requirement = TargetRequirement(
                filter_fn=lambda obj: obj in legal_targets,
                description="target player",
                # Engine note: players are not zone-backed objects, but the
                # target API currently requires a Zone value.
                zone=Zone.BATTLEFIELD,
            )
            chosen = player.choose_target(legal_targets, requirement)
            if chosen not in legal_targets:
                return None
            return [chosen]

        def _effect(game: "GameState") -> None:
            from engine.game import create_token

            chosen_targets = getattr(source, "chosen_targets", [])
            if not chosen_targets:
                return
            chosen_target = chosen_targets[0]
            if chosen_target not in game.players:
                return

            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
                colors={Color.WHITE, Color.BLACK},
            )
            create_token(game, chosen_target, token)

            you = source.controller
            if you is None:
                return

            your_creatures = _count_creatures(game, you)
            source.is_prepared = any(
                player is not you and _count_creatures(game, player) > your_creatures
                for player in game.players
            )

        registration = TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_self_etb_condition(source),
            effect=_effect,
            source=self,
            controller=controller,
            choose_targets=_choose_targets,
        )
        game.trigger_manager.register(registration)

        if controller is None or not game.get_battlefield(controller).contains(source):
            return
        if len(game.trigger_manager.get_triggers_for_source(source)) != 1:
            return

        initial_event = EntersBattlefieldTriggeredEvent(permanent=source, controller=controller)
        if registration.condition is not None and not registration.condition(game, initial_event):
            return

        chosen_targets: list[Any] = []
        if registration.choose_targets is not None:
            target_selection = registration.choose_targets(game, initial_event, registration.controller)
            if target_selection is None:
                return
            chosen_targets = list(target_selection)

        stack_obj = StackObject(
            source=registration.source,
            controller=registration.controller,
            targets=chosen_targets,
            is_spell=False,
            on_resolve=lambda _g: None,
        )

        def _on_resolve(g: "GameState", *, stack_object: StackObject = stack_obj) -> None:
            registration.source.chosen_targets = list(stack_object.targets)
            registration.effect(g)

        stack_obj.on_resolve = _on_resolve
        game.stack.push(stack_obj)
