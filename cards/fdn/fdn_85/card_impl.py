"""Card implementation for Electroduplicate."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class Electroduplicate(Sorcery):
    """Electroduplicate — {2}{R} — Sorcery.

    Create a token that's a copy of target creature you control, except it
    has haste and "At the beginning of the end step, sacrifice this token."
    Flashback {2}{R}{R}

    FDN collector number 85.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Electroduplicate')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{R}'))
        kwargs.setdefault('rules_text', 'Create a token that\'s a copy of target creature you control, except it has haste and "At the beginning of the end step, sacrifice this token."\nFlashback {2}{R}{R}')
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse('{2}{R}{R}')

    def get_targets(self, game: 'GameState') -> list:
        """Target creature you control."""
        controller = self.controller
        return [TargetRequirement(filter_fn=lambda obj: CardType.CREATURE in getattr(obj, 'card_types', set()) and getattr(obj, 'controller', None) is controller, description='target creature you control', zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game: 'GameState') -> None:
        """Create token copy with haste and end-step sacrifice."""
        from engine.game import create_token, sacrifice
        from engine.triggers import TriggerRegistration
        chosen = getattr(self, 'chosen_targets', None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, 'card_types', set()):
            return
        controller = self.controller
        if controller is None:
            return
        token_kwargs: dict[str, Any] = {'name': getattr(target, 'name', 'Token'), 'subtypes': set(getattr(target, 'subtypes', set())), 'keywords': (getattr(target, 'keywords', None) or Keyword(0)) | Keyword.HASTE, 'base_power': getattr(target, 'base_power', 0), 'base_toughness': getattr(target, 'base_toughness', 0)}
        if hasattr(target, 'colors'):
            token_kwargs['colors'] = target.colors
        if hasattr(target, 'mana_cost') and target.mana_cost:
            token_kwargs['mana_cost'] = target.mana_cost
        if hasattr(target, 'rules_text'):
            token_kwargs['rules_text'] = target.rules_text
        token = Creature(**token_kwargs)
        if hasattr(target, 'card_types'):
            token.card_types = set(target.card_types)
        create_token(game, controller, token)

        def _sac_condition(game: Any, event: dict) -> bool:
            return True

        def _sac_effect(game: 'GameState') -> None:
            ctrl = getattr(token, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            if bf.contains(token):
                sacrifice(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_sac_condition, effect=_sac_effect, source=token, controller=controller))
