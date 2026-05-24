"""Card implementation for Grappling Kraken."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class GrapplingKraken(Creature):
    """Grappling Kraken — {4}{U}{U} — 5/6 — Kraken.

    Landfall — Whenever a land you control enters, tap target creature an
    opponent controls and put a stun counter on it.

    FDN collector number 39.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Grappling Kraken')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{U}{U}'))
        kwargs.setdefault('subtypes', {'Kraken'})
        kwargs.setdefault('base_power', 5)
        kwargs.setdefault('base_toughness', 6)
        kwargs.setdefault('rules_text', 'Landfall — Whenever a land you control enters, tap target creature an opponent controls and put a stun counter on it.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register landfall trigger: tap + stun counter on opponent creature."""
        from benchmarks.sos.workspace.engine.game import add_counter
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _landfall_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            permanent = event.permanent
            if permanent is None:
                return False
            card_types = getattr(permanent, 'card_types', set())
            if CardType.LAND not in card_types:
                return False
            perm_ctrl = getattr(permanent, 'controller', None)
            if perm_ctrl is None:
                bf = game.get_battlefield(ctrl)
                return bf.contains(permanent)
            return perm_ctrl is ctrl

        def _landfall_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            target = None
            chosen = getattr(source, 'chosen_targets', None)
            if chosen:
                target = chosen[0]
                valid = False
                for player in game.players:
                    if player is ctrl:
                        continue
                    bf = game.get_battlefield(player)
                    if bf.contains(target):
                        valid = True
                        break
                if not valid:
                    target = None
            else:
                candidates: list = []
                for player in game.players:
                    if player is ctrl:
                        continue
                    bf = game.get_battlefield(player)
                    for obj in bf.get_all():
                        card_types = getattr(obj, 'card_types', set())
                        if CardType.CREATURE in card_types:
                            candidates.append(obj)
                if candidates:
                    target = candidates[0]
            if target is None:
                return
            target.is_tapped = True
            target.tapped = True
            target.stun_counters = getattr(target, 'stun_counters', 0) + 1
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_landfall_condition, effect=_landfall_effect, source=self, controller=controller))
