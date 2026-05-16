"""Card implementation for Midnight Snack."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Enchantment, Creature, ActivatedAbility
from engine.types import CardType, ManaCost, Zone
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class MidnightSnack(Enchantment):
    """Midnight Snack — {2}{B} — Enchantment.

    Raid — At the beginning of your end step, if you attacked this turn,
    create a Food token.
    {2}{B}, Sacrifice this enchantment: Target opponent loses X life, where
    X is the amount of life you gained this turn.

    FDN collector number 65.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Midnight Snack')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{B}'))
        kwargs.setdefault('rules_text', 'Raid — At the beginning of your end step, if you attacked this turn, create a Food token.\n{2}{B}, Sacrifice this enchantment: Target opponent loses X life, where X is the amount of life you gained this turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register end step trigger for Raid Food creation."""
        from engine.triggers import TriggerRegistration
        from engine.game import create_token
        source = self

        def _condition(game: Any, event: dict) -> bool:
            controller = getattr(source, 'controller', None)
            if controller is None:
                return False
            return getattr(controller, 'attacked_this_turn', False)

        def _effect(game: 'GameState') -> None:
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            from engine.card import Artifact
            food = Artifact(name='Food', subtypes={'Food'}, is_token=True)
            create_token(game, controller, food)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))

    def get_activated_abilities(self, game: 'GameState') -> list:
        """Sacrifice ability: target opponent loses X life."""
        source = self

        def _sac_effect(game: 'GameState') -> None:
            from engine.game import sacrifice
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            life_gained = getattr(controller, 'life_gained_this_turn', 0)
            sacrifice(game, controller, source)
            opponents = [p for p in game.players if p is not controller]
            if opponents and life_gained > 0:
                target = opponents[0]
                target.life -= life_gained

        def _sac_cost(game: 'GameState', src=self) -> bool:
            """Pay {2}{B} mana cost for the sacrifice ability."""
            controller = getattr(src, 'controller', None)
            if controller is None:
                return False
            cost = ManaCost.parse('{2}{B}')
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True
        ability = ActivatedAbility(cost=_sac_cost, effect=_sac_effect, description='{2}{B}, Sacrifice this enchantment: Target opponent loses X life, where X is the amount of life you gained this turn.')
        ability.tap_cost = False
        return [ability]
