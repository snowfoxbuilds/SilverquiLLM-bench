"""Card implementation for High-Society Hunter."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent, CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class HighSocietyHunter(Creature):
    """High-Society Hunter — {3}{B}{B} — 5/3 — Vampire Noble — Flying.

    Whenever this creature attacks, you may sacrifice another creature.
    If you do, put a +1/+1 counter on this creature.
    Whenever another nontoken creature dies, draw a card.

    FDN collector number 61.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'High-Society Hunter')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{B}{B}'))
        kwargs.setdefault('subtypes', {'Vampire', 'Noble'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 5)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Flying\nWhenever this creature attacks, you may sacrifice another creature. If you do, put a +1/+1 counter on this creature.\nWhenever another nontoken creature dies, draw a card.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger (sacrifice for +1/+1 counter) and death
        trigger (draw when another nontoken creature dies)."""
        from benchmarks.sos.workspace.engine.game import add_counter, draw_card, sacrifice
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self

        def _attack_condition(game: Any, event: dict) -> bool:
            """Fire when this creature attacks."""
            return event.creature is source

        def _attack_effect(game: 'GameState') -> None:
            """May sacrifice another creature; if so, add +1/+1 counter."""
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            battlefield = game.get_battlefield(controller)
            candidates = [c for c in battlefield.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and c is not source]
            if not candidates:
                return
            try:
                chosen = controller.choose_card(candidates, 'sacrifice a creature for +1/+1 counter')
            except Exception:
                chosen = None
            if chosen is None:
                return
            sacrifice(game, controller, chosen)
            add_counter(game, source, '+1/+1', 1)
            if hasattr(source, '_base_plus_one_counters'):
                source._base_plus_one_counters = source.plus_one_counters

        def _dies_condition(game: Any, event: dict) -> bool:
            """Fire when another nontoken creature dies."""
            creature = event.creature
            if creature is source:
                return False
            if getattr(creature, 'is_token', False):
                return False
            return True

        def _dies_effect(game: 'GameState') -> None:
            """Draw a card."""
            controller = getattr(source, 'controller', None) or getattr(source, 'owner', None)
            if controller is not None:
                draw_card(game, controller)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller))
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_dies_condition, effect=_dies_effect, source=self, controller=controller))
