"""Card implementation for Gnarlid Colony."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, Instant, Mode, Sorcery
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, 'controller', None)

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: dict) -> bool:
        return event.permanent is source
    return _condition

class GnarlidColony(Creature):
    """Gnarlid Colony — {1}{G} — 2/2 — Beast

    Kicker {2}{G}.
    If this creature was kicked, it enters with two +1/+1 counters on it.
    Each creature you control with a +1/+1 counter on it has trample.

    FDN collector number 224.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Gnarlid Colony')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{G}'))
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('subtypes', {'Beast'})
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse('{2}{G}')

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration

        def _etb_effect(g: GameState) -> None:
            if self.kicked:
                self.plus_one_counters += 2
                self._base_plus_one_counters = self.plus_one_counters
        reg = TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_etb_effect, source=self, controller=self.controller or self.owner)
        game.trigger_manager.register(reg)

    def get_continuous_effects(self) -> list[Any]:
        """Grant trample to each creature you control with a +1/+1 counter."""
        from engine.continuous_effects import ContinuousEffect, Layer, SubLayer

        def _apply(g: GameState) -> None:
            controller = _get_controller(self)
            if controller is None:
                return
            for obj in g.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, 'card_types', set()) and getattr(obj, 'plus_one_counters', 0) > 0:
                    obj.keywords = obj.keywords | Keyword.TRAMPLE
        # Ability-granting effect: Layer 6 (ABILITY), no sublayer (sublayers
        # are a Layer 7 P/T concept). The prior ``Layer.ABILITY_ADDING`` /
        # ``SubLayer.DEFAULT`` members do not exist, and the field is
        # ``sublayer``, not ``sub_layer`` — three errors on one line.
        return [ContinuousEffect(source=self, layer=Layer.ABILITY, apply=_apply)]
