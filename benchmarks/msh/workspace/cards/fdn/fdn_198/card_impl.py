"""Card implementation for Flamewake Phoenix."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.card_queries import query_yes_no
from engine.types import CardType, Keyword, ManaCost, Zone
from engine.events import BeginningOfCombatTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class FlamewakePhoenix(Creature):
    """Flamewake Phoenix — {1}{R}{R} — 2/2 — Phoenix — Flying, Haste.

    This creature attacks each combat if able.
    Ferocious — At the beginning of combat on your turn, if you control a
    creature with power 4 or greater, you may pay {R}. If you do, return
    this card from your graveyard to the battlefield.

    FDN collector number 198.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Flamewake Phoenix')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{R}{R}'))
        kwargs.setdefault('subtypes', {'Phoenix'})
        kwargs.setdefault('keywords', Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Flying, haste\nThis creature attacks each combat if able.\nFerocious — At the beginning of combat on your turn, if you control a creature with power 4 or greater, you may pay {R}. If you do, return this card from your graveyard to the battlefield.')
        super().__init__(**kwargs)
        self.must_attack = True

    def register_triggers(self, game: 'GameState') -> None:
        """Register beginning-of-combat graveyard recursion trigger."""
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None) or getattr(source, 'owner', None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            gy = ctrl.zones[Zone.GRAVEYARD]
            if not gy.contains(source):
                return False
            bf = game.get_battlefield(ctrl)
            for perm in bf.get_all():
                if CardType.CREATURE in getattr(perm, 'card_types', set()):
                    if perm.power >= 4:
                        return True
            return False

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None) or getattr(source, 'owner', None)
            if ctrl is None:
                return
            if not query_yes_no(game, ctrl, 'Pay {R} to return Flamewake Phoenix from graveyard?', source_card=source):
                return
            if not ctrl.mana_pool.pay(ManaCost.parse('{R}')):
                return  # insufficient mana -- pay() returns False, never raises
            move_to_zone(game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            source.controller = ctrl
        game.trigger_manager.register(TriggerRegistration(event_type=BeginningOfCombatTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
