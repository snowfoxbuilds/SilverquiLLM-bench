"""Card implementation for Vampire Gourmand."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, ManaCost, Zone
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class VampireGourmand(Creature):
    """Vampire Gourmand — {1}{B} — 2/2 — Vampire.

    Whenever this creature attacks, you may sacrifice another creature.
    If you do, draw a card and this creature can't be blocked this turn.

    FDN collector number 74.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Vampire Gourmand')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}'))
        kwargs.setdefault('subtypes', {'Vampire'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', "Whenever this creature attacks, you may sacrifice another creature. If you do, draw a card and this creature can't be blocked this turn.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for sacrifice/draw/unblockable."""
        from engine.triggers import TriggerRegistration
        from engine.game import draw_card, sacrifice
        source = self

        def _condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _effect(game: 'GameState') -> None:
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            bf = game.get_battlefield(controller)
            candidates = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and c is not source]
            if not candidates:
                return
            try:
                chosen = controller.choose_card(candidates, 'sacrifice a creature for draw + unblockable')
            except Exception:
                chosen = candidates[0] if candidates else None
            if chosen is None:
                return
            sacrifice(game, controller, chosen)
            draw_card(game, controller)
            source._cant_be_blocked = True
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
