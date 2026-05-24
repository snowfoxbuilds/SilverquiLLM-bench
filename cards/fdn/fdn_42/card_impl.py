"""Card implementation for Icewind Elemental."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from cards.registry import CardRegistry

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: dict) -> bool:
        return event.permanent is source
    return _condition

class IcewindElemental(Creature):
    """Icewind Elemental — {4}{U} — 3/4 — Elemental — Flying

    When this creature enters, draw a card, then discard a card.

    FDN collector number 42.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Icewind Elemental')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{U}'))
        kwargs.setdefault('subtypes', {'Elemental'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Flying\nWhen this creature enters, draw a card, then discard a card.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.game import draw_card, discard
        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, 'controller', None)
            if controller is not None:
                drawn = draw_card(game, controller)
                hand = game.get_hand(controller)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        to_discard = controller.choose_card(hand_cards)
                    except Exception:
                        to_discard = hand_cards[-1]
                    discard(game, controller, to_discard)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
