"""Card implementation for Grave Researcher // Reanimate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import BeginningOfUpkeepTriggeredEvent, LosesLifeTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Reanimate(Sorcery):
    """Prepared spell copy for Grave Researcher."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Reanimate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault(
            "rules_text",
            "Put target creature card from a graveyard onto the battlefield under your control. "
            "You lose life equal to its mana value.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        def _filter(card: object) -> bool:
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return False
            return any(game.get_graveyard(player).contains(card) for player in game.players)

        candidates = [
            card
            for player in game.players
            for card in game.get_graveyard(player).get_all()
            if _filter(card)
        ]
        if not candidates:
            return []
        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target creature card from a graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if controller is None or target is None:
            return

        source_graveyard_owner = next(
            (player for player in game.players if game.get_graveyard(player).contains(target)),
            None,
        )
        if source_graveyard_owner is None:
            return

        mana_value = getattr(getattr(target, "mana_cost", None), "cmc", 0)
        target.controller = controller
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        controller.life -= mana_value
        game.trigger_manager.fire_event(
            game,
            LosesLifeTriggeredEvent(player=controller, amount=mana_value),
        )


class GraveResearcherReanimate(Creature):
    """Grave Researcher."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grave Researcher")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Troll", "Warlock"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "At the beginning of your upkeep, surveil 1. Then if there are three or more "
            "creature cards in your graveyard, this creature becomes prepared.",
        )
        super().__init__(**kwargs)

    def create_prepared_spell_copy(self) -> Sorcery:
        return Reanimate(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and game.active_player is current_controller
                and source.is_on_battlefield(game)
            )

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return

            library = game.get_library(current_controller)
            if len(library) > 0:
                top_card = library.top(1)[0]
                if current_controller.choose_yes_no("Put the top card of your library into your graveyard?"):
                    move_to_zone(game, top_card, Zone.LIBRARY, Zone.GRAVEYARD)

            graveyard = game.get_graveyard(current_controller)
            creature_count = sum(1 for card in graveyard.get_all() if isinstance(card, Creature))
            if creature_count >= 3:
                source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
