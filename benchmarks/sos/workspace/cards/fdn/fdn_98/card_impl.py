"""Card implementation for Ambush Wolf."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
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

class AmbushWolf(Creature):
    """Ambush Wolf — {2}{G} — 4/2 — Wolf — Flash

    When this creature enters, exile up to one target card from a graveyard.

    FDN collector number 98.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Ambush Wolf')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}'))
        kwargs.setdefault('subtypes', {'Wolf'})
        kwargs.setdefault('keywords', Keyword.FLASH)
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Flash\nWhen this creature enters, exile up to one target card from a graveyard.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is None:
                return
            for player in game.players:
                gy = player.zones[Zone.GRAVEYARD]
                if gy.contains(target):
                    gy.remove(target)
                    owner = getattr(target, 'owner', player)
                    owner.zones[Zone.EXILE].add(target)
                    return
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
