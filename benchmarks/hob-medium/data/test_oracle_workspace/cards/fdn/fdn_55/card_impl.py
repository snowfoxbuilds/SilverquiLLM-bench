"""Card implementation for Arbiter of Woe."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.card_queries import choose_object
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

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
        from engine.triggers import TriggerRegistration
        from engine.game import draw_card, discard
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
                    to_discard = choose_object(game, player, hand_cards, 'card to discard', source_card=source)
                    discard(game, player, to_discard)
                from engine.game import lose_life
                lose_life(game, player, 2)
            draw_card(game, controller)
            from engine.game import gain_life
            gain_life(game, controller, 2)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
