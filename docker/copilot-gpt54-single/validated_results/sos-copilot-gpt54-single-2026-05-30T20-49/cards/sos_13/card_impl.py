"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _self_etb_condition(source: Any):
    """Match only this permanent entering the battlefield."""

    def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
        return event.permanent is source

    return _condition


def _is_player_target(obj: Any) -> bool:
    """Return whether *obj* is a player-like battlefield target."""
    return hasattr(obj, "life") and not hasattr(obj, "card_types")


class PreparedSwordsToPlowshares(Instant):
    """Minimal prepared spell copy created by Emeritus of Truce."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce front face with a testable prepared subset."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
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
        self.is_prepared: bool = False
        self.prepared_copy: Instant | None = None

    def _target_requirements(self) -> list[TargetRequirement]:
        """Return the ETB trigger's target requirements."""
        return [
            TargetRequirement(
                filter_fn=_is_player_target,
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def _clear_prepared_copy(self, game: "GameState") -> None:
        """Remove any lingering prepared spell copy from exile."""
        prepared_copy = self.prepared_copy
        if prepared_copy is not None:
            for player in game.players:
                exile = game.get_exile(player)
                if exile.contains(prepared_copy):
                    exile.remove(prepared_copy)
                    break
        self.prepared_copy = None

    def _set_prepared(self, game: "GameState", prepared: bool) -> None:
        """Update prepared state and maintain the prepared-copy lifetime."""
        if not prepared:
            self.is_prepared = False
            self._clear_prepared_copy(game)
            return

        source_controller = self.controller
        if source_controller is None:
            return

        self.is_prepared = True
        if self.prepared_copy is not None:
            return

        prepared_copy = PreparedSwordsToPlowshares(
            owner=source_controller,
            controller=source_controller,
        )
        self.prepared_copy = prepared_copy
        game.get_exile(source_controller).add(prepared_copy)

    def _resolve_etb(self, game: "GameState") -> None:
        """Create the Inkling token, then prepare if counts now favor an opponent."""
        from engine.game import create_token

        chosen_targets = getattr(self, "chosen_targets", [])
        target_player = chosen_targets[0] if chosen_targets else None
        if target_player is None or not _is_player_target(target_player):
            return

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
            owner=target_player,
            controller=target_player,
        )
        create_token(game, target_player, token)

        source_controller = self.controller
        if source_controller is None:
            return

        if not game.get_battlefield(source_controller).contains(self):
            return

        your_creatures = sum(
            1
            for obj in game.get_battlefield(source_controller).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )
        opponent_has_more = any(
            sum(
                1
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )
            > your_creatures
            for player in game.players
            if player is not source_controller
        )
        if not opponent_has_more:
            return

        self._set_prepared(game, True)

    def _queue_etb_trigger(self, game: "GameState") -> None:
        """Put the targeted ETB ability onto the stack."""
        from engine.casting import get_target_options, validate_target_choice

        controller = self.controller or self.owner or game.active_player
        requirements = self._target_requirements()
        chosen_targets: list[Any] = []
        for requirement in requirements:
            options = get_target_options(game, requirement)
            if not options:
                return
            chosen = controller.choose_target(options, requirement)
            if not validate_target_choice(options, requirement, chosen):
                raise ValueError(
                    "Emeritus of Truce received an illegal ETB target choice"
                )
            chosen_targets.append(chosen)

        def _ability_on_resolve(g: "GameState") -> None:
            self.chosen_targets = chosen_targets
            self._resolve_etb(g)

        game.stack.push(
            StackObject(
                source=self,
                controller=controller,
                targets=chosen_targets,
                target_requirements=requirements,
                on_resolve=_ability_on_resolve,
                is_spell=False,
            )
        )

    def on_resolve(self, game: "GameState") -> None:
        """Front-face spell resolution has no extra spell-only work."""

    def on_enters_battlefield(self, game: "GameState") -> None:
        """Queue the ETB trigger for any battlefield entry route."""
        self._queue_etb_trigger(game)

    def on_leaves_battlefield(self, game: "GameState") -> None:
        """Prepared copies only persist while this stays prepared on the battlefield."""
        self._set_prepared(game, False)

    def unprepare(self, game: "GameState") -> None:
        """Public helper for future prepared-spell casting flows."""
        self._set_prepared(game, False)

    def register_triggers(self, game: "GameState") -> None:
        """Register Emeritus of Truce's targeted ETB trigger."""
        source = self
        controller = self.controller or self.owner or game.active_player

        def _requirements(
            game: "GameState",
            event: EntersBattlefieldTriggeredEvent,
        ) -> list[TargetRequirement]:
            return source._target_requirements()

        def _effect(game: "GameState") -> None:
            source._resolve_etb(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition(source),
                effect=_effect,
                source=source,
                controller=controller,
                target_requirements=_requirements,
            )
        )
