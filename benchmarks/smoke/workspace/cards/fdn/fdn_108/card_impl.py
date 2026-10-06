"""Card implementation for Needletooth Pack."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EndStepTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class NeedletoothPackAbility1:
    text = 'Morbid — At the beginning of your end step, if a creature died this turn, put two +1/+1 counters on target creature you control.'


# endregion Printed abilities


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class NeedletoothPack(Creature):
    """Needletooth Pack — {3}{G}{G} — 4/5 — Dinosaur.

    Morbid — At the beginning of your end step, if a creature died this
    turn, put two +1/+1 counters on target creature you control.

    FDN collector number 108.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Needletooth Pack')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{G}{G}'))
        kwargs.setdefault('subtypes', {'Dinosaur'})
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 5)
        kwargs.setdefault('rules_text', 'Morbid — At the beginning of your end step, if a creature died this turn, put two +1/+1 counters on target creature you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.game import add_counter
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if game.active_player is not controller:
                return False
            return getattr(game, 'creature_died_this_turn', False)

        def _targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any] | None:
            return choose_trigger_targets(game, ctrl, source, [TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, 'card_types', set()) and getattr(obj, 'controller', None) is ctrl,
                description='creature to put +1/+1 counters on', zone=Zone.BATTLEFIELD)])

        def _effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            (target,) = stint_checked_targets(game, context, targets)
            if target is not None and getattr(target, 'controller', None) is context.controller:
                add_counter(game, target, '+1/+1', 2)
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, targeting=_targeting, printed=NeedletoothPackAbility1))
