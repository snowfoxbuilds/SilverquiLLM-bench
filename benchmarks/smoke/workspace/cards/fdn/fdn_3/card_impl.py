"""Card implementation for Armasaur Guide."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ArmasaurGuideAbility1:
    text = "Vigilance (Attacking doesn't cause this creature to tap.)"


class ArmasaurGuideAbility2:
    text = 'Whenever you attack with three or more creatures, put a +1/+1 counter on target creature you control.'


# endregion Printed abilities


class ArmasaurGuide(Creature):
    """Armasaur Guide — {4}{W} — 4/4 — Dinosaur — Vigilance.

    Whenever you attack with three or more creatures, put a +1/+1 counter
    on target creature you control.

    FDN collector number 3.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Armasaur Guide')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{W}'))
        kwargs.setdefault('subtypes', {'Dinosaur'})
        kwargs.setdefault('keywords', Keyword.VIGILANCE)
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Vigilance\nWhenever you attack with three or more creatures, put a +1/+1 counter on target creature you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger: 3+ attackers → +1/+1 counter on target."""
        from engine.game import add_counter
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _attack_condition(game: Any, event: dict) -> bool:
            """Fire when controller attacks with 3+ creatures."""
            attacker = event.creature
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            battlefield = game.get_battlefield(ctrl)
            attacking = [c for c in battlefield.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and getattr(c, 'is_attacking', False)]
            return len(attacking) >= 3 and attacker is source

        def _targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any] | None:
            return choose_trigger_targets(game, ctrl, source, [TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, 'card_types', set()) and getattr(obj, 'controller', None) is ctrl,
                description='target creature for +1/+1 counter', zone=Zone.BATTLEFIELD)])

        def _attack_effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            """Put a +1/+1 counter on target creature you control."""
            (target,) = stint_checked_targets(game, context, targets)
            if target is not None and getattr(target, 'controller', None) is context.controller:
                add_counter(game, target, '+1/+1', 1)
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller, targeting=_targeting, printed=ArmasaurGuideAbility2))
