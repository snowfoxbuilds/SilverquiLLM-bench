"""Card implementation for Meteor Golem."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: dict) -> bool:
        return event.permanent is source
    return _condition

def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, 'chosen_targets', None)
    if chosen:
        return chosen[0]
    return getattr(card, '_resolve_target', None)

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class MeteorGolem(ArtifactCreature):
    """Meteor Golem — {7} — 3/3 — Golem

    When this creature enters, destroy target nonland permanent an opponent controls.

    FDN collector number 256.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Meteor Golem')
        kwargs.setdefault('mana_cost', ManaCost.parse('{7}'))
        kwargs.setdefault('subtypes', {'Golem'})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'When this creature enters, destroy target nonland permanent an opponent controls.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.game import destroy
        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and _is_on_battlefield(game, target):
                destroy(game, target)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
