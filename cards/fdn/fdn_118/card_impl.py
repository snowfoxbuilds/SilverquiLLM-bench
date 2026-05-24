"""Card implementation for Dreadwing Scavenger."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class DreadwingScavenger(Creature):
    """Dreadwing Scavenger — {1}{U}{B} — 2/2 — Nightmare Bird.

    Flying
    Whenever this creature enters or attacks, draw a card, then discard
    a card.
    Threshold — This creature gets +1/+1 and has deathtouch as long as
    there are seven or more cards in your graveyard.

    FDN collector number 118.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Dreadwing Scavenger')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{U}{B}'))
        kwargs.setdefault('subtypes', {'Nightmare', 'Bird'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Flying\nWhenever this creature enters or attacks, draw a card, then discard a card.\nThreshold — This creature gets +1/+1 and has deathtouch as long as there are seven or more cards in your graveyard.')
        super().__init__(**kwargs)
        self._threshold_effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: 'GameState') -> None:
        """ETB: draw a card, then discard a card."""
        from benchmarks.sos.workspace.engine.game import draw_card, discard
        controller = self.controller
        if controller is None:
            return
        draw_card(game, controller)
        hand = list(controller.zones[Zone.HAND].get_all())
        if hand:
            try:
                chosen = controller.choose_card(hand, 'card to discard')
            except Exception:
                chosen = hand[0]
            if chosen is not None:
                discard(game, controller, chosen)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger (loot) and threshold continuous effect."""
        from benchmarks.sos.workspace.engine.game import draw_card, discard
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _attack_condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _attack_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            draw_card(game, ctrl)
            hand = list(ctrl.zones[Zone.HAND].get_all())
            if hand:
                try:
                    chosen = ctrl.choose_card(hand, 'card to discard')
                except Exception:
                    chosen = hand[0]
                if chosen is not None:
                    discard(game, ctrl, chosen)
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller))

        def _apply_threshold(game: Any) -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            if not _is_on_battlefield(game, source):
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            gy_count = len(list(graveyard.get_all()))
            if gy_count >= 7:
                source.modified_power += 1
                source.modified_toughness += 1
                source.keywords = (getattr(source, 'keywords', None) or Keyword(0)) | Keyword.DEATHTOUCH
        self._threshold_effect_ref = game.effect_manager.add(ContinuousEffect(source=self, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_threshold, duration=DURATION_PERMANENT))

    def unregister_triggers(self, game: 'GameState') -> None:
        """Clean up threshold effect when leaving battlefield."""
        if self._threshold_effect_ref is not None:
            game.effect_manager.remove(self._threshold_effect_ref)
            self._threshold_effect_ref = None
