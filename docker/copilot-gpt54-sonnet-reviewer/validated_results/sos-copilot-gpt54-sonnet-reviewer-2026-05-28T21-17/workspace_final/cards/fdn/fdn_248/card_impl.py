"""Card implementation for Thousand-Year Storm."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Enchantment
from engine.types import CardType, ManaCost
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState


class ThousandYearStorm(Enchantment):
    """Thousand-Year Storm — {4}{U}{R} — Enchantment.

    Whenever you cast an instant or sorcery spell, copy it for each
    other instant and sorcery spell you've cast before it this turn.
    You may choose new targets for the copies.

    FDN collector number 248.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Thousand-Year Storm')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{U}{R}'))
        kwargs.setdefault(
            'rules_text',
            "Whenever you cast an instant or sorcery spell, copy it for each "
            "other instant and sorcery spell you've cast before it this turn. "
            "You may choose new targets for the copies.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._storm_count: int = 0
        source._last_turn: int = getattr(game, 'turn_number', 0)

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, 'controller', None)
            caster = getattr(event, 'player', None) or getattr(event, 'controller', None)
            if caster is not ctrl:
                return False
            spell = getattr(event, 'spell', None) or getattr(event, 'card', None)
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            current_turn = getattr(game, 'turn_number', 0)
            if current_turn != source._last_turn:
                source._storm_count = 0
                source._last_turn = current_turn
            source._pending_spell = spell
            return True

        def _effect(game: 'GameState') -> None:
            copies_to_make = source._storm_count
            source._storm_count += 1
            if copies_to_make <= 0:
                return
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            pending_spell = getattr(source, '_pending_spell', None)
            if pending_spell is None:
                return
            original_so = None
            for so in game.stack._items:
                if so.source is pending_spell:
                    original_so = so
                    break
            if original_so is None:
                return
            for _ in range(copies_to_make):
                new_targets: list[Any] | None = None
                if original_so.targets:
                    if ctrl.choose_yes_no(
                        f"Choose new targets for copy of {original_so.source.name}?"
                    ):
                        requirements = getattr(
                            original_so.source, 'get_targets', lambda _: []
                        )(game)
                        new_targets = []
                        for req in requirements:
                            legal: list[Any] = []
                            for p in game.players:
                                for obj in game.get_battlefield(p).get_all():
                                    if req.filter_fn(obj):
                                        legal.append(obj)
                                if req.filter_fn(p):
                                    legal.append(p)
                            if legal:
                                chosen = ctrl.choose_target(legal, req)
                                new_targets.append(chosen)
                copy_obj = copy_spell(game, original_so, ctrl, new_targets)
                game.stack.push(copy_obj)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
