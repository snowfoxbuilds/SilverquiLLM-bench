"""Card implementation for Thousand-Year Storm."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Enchantment
from engine.card_queries import query_yes_no
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

        def _effect(game: 'GameState', controller: Any) -> None:
            from engine.casting import CastingError, _query_target

            copies_to_make = source._storm_count
            source._storm_count += 1
            if copies_to_make <= 0:
                return
            # "You" is the ability's fire-time controller, threaded in immutably by
            # the trigger engine — never re-read from source.controller (the
            # enchantment could have changed hands since the trigger fired).
            ctrl = controller
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
                    if query_yes_no(
                        game,
                        ctrl,
                        f"Choose new targets for copy of {original_so.source.name}?",
                        source_card=source,
                    ):
                        # Re-choose targets through the shared cast-time target
                        # machinery (_query_target): zone-aware, arity-aware
                        # filters (so dependent targets like "Equipment attached
                        # to that creature" work), distinctness via exclude, and
                        # protection — not a bespoke filter loop. A required spec
                        # with no legal target, or a declined optional one, keeps
                        # the original target for that position.
                        specs = original_so.source.get_targets(game)
                        new_targets = []
                        for i, spec in enumerate(specs):
                            try:
                                chosen = _query_target(
                                    game, ctrl, source, spec, exclude=new_targets
                                )
                            except CastingError:
                                chosen = None
                            if chosen is None and i < len(original_so.targets):
                                chosen = original_so.targets[i]
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
