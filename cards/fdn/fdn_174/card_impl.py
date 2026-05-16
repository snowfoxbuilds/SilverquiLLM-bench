"""Card implementation for Fake Your Own Death."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import CardImpl, Instant, Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from engine.events import CreatureDiesTriggeredEvent, EndOfTurnTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class FakeYourOwnDeath(Instant):
    """Fake Your Own Death — {1}{B} — Instant.

    Until end of turn, target creature gets +2/+0 and gains "When this
    creature dies, return it to the battlefield tapped under its owner's
    control and you create a Treasure token."

    FDN collector number 174.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Fake Your Own Death')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}'))
        kwargs.setdefault('rules_text', 'Until end of turn, target creature gets +2/+0 and gains "When this creature dies, return it to the battlefield tapped under its owner\'s control and you create a Treasure token."')
        super().__init__(**kwargs)

    def get_targets(self, game: 'GameState') -> list:
        """Target creature on the battlefield."""
        return [TargetRequirement(filter_fn=lambda obj: CardType.CREATURE in getattr(obj, 'card_types', set()), description='target creature', zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game: 'GameState') -> None:
        """Apply +2/+0 and death trigger until end of turn."""
        from engine.game import create_token
        from engine.zones import move_to_zone
        from engine.triggers import TriggerRegistration
        chosen = getattr(self, 'chosen_targets', None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, 'card_types', set()):
                    still_valid = True
                    break
        if not still_valid:
            return
        creature_ref = target
        spell_controller = self.controller

        def _apply_buff(game: Any) -> None:
            creature_ref.base_power += 2
        game.effect_manager.add(ContinuousEffect(source=self, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_buff, duration=DURATION_END_OF_TURN))

        def _death_condition(game: Any, event: dict) -> bool:
            return event.creature is creature_ref

        def _death_effect(game: 'GameState') -> None:
            owner = getattr(creature_ref, 'owner', spell_controller)
            move_to_zone(game, creature_ref, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            creature_ref.is_tapped = True
            creature_ref.controller = owner
            if spell_controller is not None:
                treasure = CardImpl(name='Treasure', mana_cost=ManaCost(generic=0), rules_text='{T}, Sacrifice this token: Add one mana of any color.')
                treasure.card_types = {CardType.ARTIFACT}
                treasure.subtypes = {'Treasure'}
                treasure.is_token = True
                create_token(game, spell_controller, treasure)
        controller = getattr(self, 'controller', None) or game.active_player

        class _DeathTriggerSentinel:
            pass
        sentinel = _DeathTriggerSentinel()
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_death_condition, effect=_death_effect, source=sentinel, controller=controller))
        _sentinel_ref = sentinel

        def _eot_cleanup_condition(game: Any, event: dict) -> bool:
            return True

        def _eot_cleanup_effect(game: 'GameState') -> None:
            game.trigger_manager.unregister(_sentinel_ref)
        if hasattr(EventType, 'END_OF_TURN'):
            game.trigger_manager.register(TriggerRegistration(event_type=EndOfTurnTriggeredEvent, condition=_eot_cleanup_condition, effect=_eot_cleanup_effect, source=sentinel, controller=controller))
