"""Card implementation for Arbiter of Woe."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: dict) -> bool:
        return event.permanent is source
    return _condition

class ArbiterOfWoe(Creature):
    """Arbiter of Woe — {4}{B}{B} — 5/4 — Demon — Flying

    As an additional cost to cast this spell, sacrifice a creature.
    Flying
    When this creature enters, each opponent discards a card and loses 2 life.
    You draw a card and gain 2 life.

    FDN collector number 55.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Arbiter of Woe')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{B}{B}'))
        kwargs.setdefault('subtypes', {'Demon'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 5)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'As an additional cost to cast this spell, sacrifice a creature.\nFlying\nWhen this creature enters, each opponent discards a card and loses 2 life. You draw a card and gain 2 life.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.game import draw_card, discard
        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            for player in game.players:
                if player is controller:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        to_discard = player.choose_card(hand_cards)
                    except Exception:
                        to_discard = hand_cards[-1]
                    discard(game, player, to_discard)
                player.life -= 2
            draw_card(game, controller)
            controller.life += 2
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
