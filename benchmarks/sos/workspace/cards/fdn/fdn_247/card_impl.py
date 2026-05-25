"""Card implementation for Tatyova, Benthic Druid."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Supertype
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class TatyovaBenthicDruid(Creature):
    """Tatyova, Benthic Druid — {3}{G}{U} — 3/3 — Legendary Merfolk Druid.

    Landfall — Whenever a land you control enters, you gain 1 life and
    draw a card.

    FDN collector number 247.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Tatyova, Benthic Druid')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{G}{U}'))
        kwargs.setdefault('subtypes', {'Merfolk', 'Druid'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Landfall — Whenever a land you control enters, you gain 1 life and draw a card.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register landfall trigger."""
        from benchmarks.sos.workspace.engine.game import draw_card
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            permanent = event.permanent
            if permanent is None:
                return False
            if CardType.LAND not in getattr(permanent, 'card_types', set()):
                return False
            perm_ctrl = getattr(permanent, 'controller', None)
            if perm_ctrl is None:
                bf = game.get_battlefield(ctrl)
                return bf.contains(permanent)
            return perm_ctrl is ctrl

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            ctrl.life += 1
            draw_card(game, ctrl)
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
