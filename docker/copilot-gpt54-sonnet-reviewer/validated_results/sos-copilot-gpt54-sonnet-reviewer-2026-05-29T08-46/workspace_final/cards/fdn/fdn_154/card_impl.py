"""Card implementation for Extravagant Replication."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Enchantment
from engine.types import CardType, ManaCost, Zone
from engine.events import BeginningOfUpkeepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class ExtravagantReplication(Enchantment):
    """Extravagant Replication — {4}{U}{U} — Enchantment.

    At the beginning of your upkeep, create a token that's a copy of
    another target nonland permanent you control.

    FDN collector number 154.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Extravagant Replication')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{U}{U}'))
        kwargs.setdefault('rules_text', "At the beginning of your upkeep, create a token that's a copy of another target nonland permanent you control.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register upkeep trigger to copy a nonland permanent."""
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            return game.active_player is ctrl

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            candidates = []
            for obj in bf.get_all():
                if obj is source:
                    continue
                card_types = getattr(obj, 'card_types', set())
                if CardType.LAND in card_types and len(card_types) == 1:
                    continue
                if CardType.LAND not in card_types:
                    candidates.append(obj)
            if not candidates:
                return
            try:
                chosen = ctrl.choose_card(candidates, 'Choose a nonland permanent to copy')
            except Exception:
                chosen = candidates[0] if candidates else None
            if chosen is None:
                return
            import copy
            token = copy.copy(chosen)
            token.is_token = True
            create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=BeginningOfUpkeepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
