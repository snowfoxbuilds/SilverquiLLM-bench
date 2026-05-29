"""Card implementation for Kellan, Planar Trailblazer."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature
from engine.types import Keyword, ManaCost, Supertype, Zone
from engine.events import DealsDamageTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class KellanPlanarTrailblazer(Creature):
    """Kellan, Planar Trailblazer — {R} — 2/1 — Legendary Human Faerie Scout.

    {1}{R}: If Kellan is a Scout, it becomes a Human Faerie Detective and
    gains "Whenever Kellan deals combat damage to a player, exile the top
    card of your library. You may play that card this turn."
    {2}{R}: If Kellan is a Detective, it becomes a 3/2 Human Faerie Rogue
    and gains double strike.

    FDN collector number 91.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Kellan, Planar Trailblazer')
        kwargs.setdefault('mana_cost', ManaCost.parse('{R}'))
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('subtypes', {'Human', 'Faerie', 'Scout'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', '{1}{R}: If Kellan is a Scout, it becomes a Human Faerie Detective and gains "Whenever Kellan deals combat damage to a player, exile the top card of your library. You may play that card this turn."\n{2}{R}: If Kellan is a Detective, it becomes a 3/2 Human Faerie Rogue and gains double strike.')
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the two level-up style activated abilities."""
        source = self

        def _cost_scout(game: 'GameState') -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            return ctrl.mana_pool.pay(ManaCost.parse('{1}{R}'))

        def _effect_scout(game: 'GameState') -> None:
            if 'Scout' not in getattr(source, 'subtypes', set()):
                return
            source.subtypes = {'Human', 'Faerie', 'Detective'}
            source._kellan_has_detective_trigger = True

        def _cost_detective(game: 'GameState') -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            return ctrl.mana_pool.pay(ManaCost.parse('{2}{R}'))

        def _effect_detective(game: 'GameState') -> None:
            if 'Detective' not in getattr(source, 'subtypes', set()):
                return
            source.subtypes = {'Human', 'Faerie', 'Rogue'}
            source.modified_power = 3
            source.modified_toughness = 2
            source.keywords = (getattr(source, 'keywords', None) or Keyword(0)) | Keyword.DOUBLE_STRIKE
        return [ActivatedAbility(cost=_cost_scout, effect=_effect_scout, description='{1}{R}: Become Detective with combat damage exile ability.'), ActivatedAbility(cost=_cost_detective, effect=_effect_detective, description='{2}{R}: Become 3/2 Rogue with double strike.')]

    def register_triggers(self, game: 'GameState') -> None:
        """Register combat damage trigger for Detective mode."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if not getattr(source, '_kellan_has_detective_trigger', False):
                return False
            if event.source is not source:
                return False
            target = event.target
            if not hasattr(target, 'life'):
                return False
            return getattr(event, 'is_combat', True)

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            cards = list(library.get_all())
            if not cards:
                return
            top_card = cards[-1]
            from engine.zones import move_to_zone
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            if hasattr(game, 'grant_temporary_play_permission'):
                game.grant_temporary_play_permission(top_card, ctrl, duration='this_turn')
            top_card._playable_this_turn = True
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
