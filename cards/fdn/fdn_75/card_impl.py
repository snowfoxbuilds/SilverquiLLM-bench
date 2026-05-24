"""Card implementation for Vampire Soulcaller."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from cards.registry import CardRegistry

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

class VampireSoulcaller(Creature):
    """Vampire Soulcaller — {4}{B} — 3/2 — Vampire Warlock — Flying

    This creature can't block.
    When this creature enters, return target creature card from your
    graveyard to your hand.

    FDN collector number 75.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Vampire Soulcaller')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{B}'))
        kwargs.setdefault('subtypes', {'Vampire', 'Warlock'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', "Flying\nThis creature can't block.\nWhen this creature enters, return target creature card from your graveyard to your hand.")
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            controller = getattr(source, 'controller', None)
            if target is None or controller is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            if gy.contains(target):
                gy.remove(target)
                controller.zones[Zone.HAND].add(target)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
