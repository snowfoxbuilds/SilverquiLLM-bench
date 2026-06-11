"""Card implementation for Zimone, Paradox Sculptor."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.types import CardType, ManaCost, Zone
from engine.events import BeginningOfCombatTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class ZimoneParadoxSculptor(Creature):
    """Zimone, Paradox Sculptor — {2}{G}{U} — 1/4 — Legendary Human Wizard.

    At the beginning of combat on your turn, put a +1/+1 counter on each
    of up to two target creatures you control.
    {G}{U}, {T}: Double the number of each kind of counter on up to two
    target creatures and/or artifacts you control.

    FDN collector number 126.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Zimone, Paradox Sculptor')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}{U}'))
        kwargs.setdefault('subtypes', {'Human', 'Wizard'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'At the beginning of combat on your turn, put a +1/+1 counter on each of up to two target creatures you control.\n{G}{U}, {T}: Double the number of each kind of counter on up to two target creatures and/or artifacts you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register beginning-of-combat trigger for +1/+1 counters."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            return game.active_player is ctrl

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            candidates = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set())]
            if not candidates:
                return
            targets_chosen = []
            for i in range(min(2, len(candidates))):
                remaining = [c for c in candidates if c not in targets_chosen]
                if not remaining:
                    break
                try:
                    chosen = choose_object(game, ctrl, remaining, f'creature to get +1/+1 counter ({i + 1}/2)', source_card=source)
                except Exception:
                    chosen = remaining[0] if remaining else None
                if chosen is not None:
                    targets_chosen.append(chosen)
            for target in targets_chosen:
                add_counter(game, target, '+1/+1')
                target._base_plus_one_counters = target.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=BeginningOfCombatTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))

    def get_activated_abilities(self, game: 'GameState') -> list:
        """{G}{U}, {T}: Double counters on up to two targets."""
        source = self

        def _double_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            candidates = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) or CardType.ARTIFACT in getattr(c, 'card_types', set())]
            if not candidates:
                return
            targets_chosen = []
            for i in range(min(2, len(candidates))):
                remaining = [c for c in candidates if c not in targets_chosen]
                if not remaining:
                    break
                try:
                    chosen = choose_object(game, ctrl, remaining, f'creature/artifact to double counters ({i + 1}/2)', source_card=source)
                except Exception:
                    chosen = remaining[0] if remaining else None
                if chosen is not None:
                    targets_chosen.append(chosen)
            for target in targets_chosen:
                plus_one = getattr(target, 'plus_one_counters', 0)
                if plus_one > 0:
                    from engine.game import add_counter
                    add_counter(game, target, '+1/+1', plus_one)
                    target._base_plus_one_counters = target.plus_one_counters
                minus_one = getattr(target, 'minus_one_counters', 0)
                if minus_one > 0:
                    from engine.game import add_counter as _add
                    _add(game, target, '-1/-1', minus_one)
                loyalty = getattr(target, 'loyalty', 0)
                if loyalty > 0 and hasattr(target, 'loyalty'):
                    from engine.game import add_counter as _add2
                    _add2(game, target, 'loyalty', loyalty)
                generic = {}
                if hasattr(target, 'counters') and isinstance(target.counters, dict):
                    pass
                raw_counters = target.__dict__.get('counters', None)
                if raw_counters and isinstance(raw_counters, dict):
                    generic = dict(raw_counters)
                for ctype, count in generic.items():
                    if ctype in ('+1/+1', '-1/-1'):
                        continue
                    if count > 0:
                        from engine.game import add_counter as _add3
                        _add3(game, target, ctype, count)

        def _cost(game: 'GameState', src: Any=source) -> bool:
            if getattr(src, 'is_tapped', False):
                return False
            ctrl = getattr(src, 'controller', None)
            if ctrl is None:
                return False
            mana_cost = ManaCost.parse('{G}{U}')
            if not ctrl.mana_pool.can_pay(mana_cost):
                return False
            src.is_tapped = True
            ctrl.mana_pool.pay(mana_cost)
            return True
        ability = ActivatedAbility(cost=_cost, effect=_double_effect, description='{G}{U}, {T}: Double counters on up to two target creatures/artifacts.')
        ability.tap_cost = True
        return [ability]
