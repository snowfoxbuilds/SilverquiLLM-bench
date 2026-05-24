"""Card implementation for Consuming Aberration."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class ConsumingAberration(Creature):
    """Consuming Aberration — {3}{U}{B} — */* — Horror.

    Consuming Aberration's power and toughness are each equal to the
    number of cards in your opponents' graveyards.
    Whenever you cast a spell, each opponent reveals cards from the top
    of their library until they reveal a land card, then puts those
    cards into their graveyard.

    FDN collector number 238.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Consuming Aberration')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{U}{B}'))
        kwargs.setdefault('subtypes', {'Horror'})
        kwargs.setdefault('base_power', 0)
        kwargs.setdefault('base_toughness', 0)
        kwargs.setdefault('rules_text', "Consuming Aberration's power and toughness are each equal to the number of cards in your opponents' graveyards.\nWhenever you cast a spell, each opponent reveals cards from the top of their library until they reveal a land card, then puts those cards into their graveyard.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register CDA for P/T and spell-cast mill trigger."""
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _apply_cda(game: Any) -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None or not _is_on_battlefield(game, source):
                return
            count = 0
            for player in game.players:
                if player is not ctrl:
                    gy = player.zones[Zone.GRAVEYARD]
                    count += len(list(gy.get_all()))
            source.modified_power = count
            source.modified_toughness = count
        game.effect_manager.add(ContinuousEffect(source=self, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.CHARACTERISTIC_DEFINING, apply=_apply_cda, duration=DURATION_PERMANENT))

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            caster = event.player or event.controller
            return caster is ctrl

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            for player in game.players:
                if player is ctrl:
                    continue
                library = player.zones[Zone.LIBRARY]
                lib_cards = list(library.get_all())
                while lib_cards:
                    card = lib_cards.pop()
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
                    card_types = getattr(card, 'card_types', set())
                    if CardType.LAND in card_types:
                        break
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
