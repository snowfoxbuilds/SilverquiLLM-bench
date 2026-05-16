"""Card implementation for Quilled Greatwurm."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from engine.events import DealsDamageTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class QuilledGreatwurm(Creature):
    """Quilled Greatwurm — {4}{G}{G} — 7/7 — Wurm — Trample.

    Whenever a creature you control deals combat damage during your turn,
    put that many +1/+1 counters on it.
    You may cast this card from your graveyard by removing six counters
    from among creatures you control in addition to paying its other costs.

    FDN collector number 111.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Quilled Greatwurm')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{G}{G}'))
        kwargs.setdefault('subtypes', {'Wurm'})
        kwargs.setdefault('keywords', Keyword.TRAMPLE)
        kwargs.setdefault('base_power', 7)
        kwargs.setdefault('base_toughness', 7)
        kwargs.setdefault('rules_text', 'Trample\nWhenever a creature you control deals combat damage during your turn, put that many +1/+1 counters on it.\nYou may cast this card from your graveyard by removing six counters from among creatures you control in addition to paying its other costs.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.game import add_counter
        from engine.player import Player
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _make_trigger(game: 'GameState') -> None:
            """Create a trigger that captures its own event data per firing."""

            def _condition_with_capture(game: Any, event: dict) -> bool:
                if not event.is_combat:
                    return False
                dmg_source = event.source
                if dmg_source is None:
                    return False
                ctrl = getattr(source, 'controller', None)
                if ctrl is None:
                    return False
                if getattr(game, 'active_player', None) is not ctrl:
                    return False
                card_types = getattr(dmg_source, 'card_types', set())
                if CardType.CREATURE not in card_types:
                    return False
                src_ctrl = getattr(dmg_source, 'controller', None)
                if src_ctrl is not ctrl:
                    return False
                _condition_with_capture._last_creature = dmg_source
                _condition_with_capture._last_amount = event.amount
                return True

            def _captured_effect(game: 'GameState') -> None:
                creature = getattr(_condition_with_capture, '_last_creature', None)
                amount = getattr(_condition_with_capture, '_last_amount', 0)
                if creature is None or amount <= 0:
                    return
                for player in game.players:
                    if game.get_battlefield(player).contains(creature):
                        add_counter(game, creature, '+1/+1', amount)
                        creature._original_plus_one_counters = creature.plus_one_counters
                        return
            game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_condition_with_capture, effect=_captured_effect, source=source, controller=controller))
        _make_trigger(game)
