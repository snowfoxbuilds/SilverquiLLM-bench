"""Card implementation for Stromkirk Bloodthief."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EndStepTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class StromkirkBloodthiefAbility1:
    text = 'At the beginning of your end step, if an opponent lost life this turn, put a +1/+1 counter on target Vampire you control.'


# endregion Printed abilities


class StromkirkBloodthief(Creature):
    """Stromkirk Bloodthief — {2}{B} — 2/2 — Vampire Rogue.

    At the beginning of your end step, if an opponent lost life this turn,
    put a +1/+1 counter on target Vampire you control.

    FDN collector number 185.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Stromkirk Bloodthief')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{B}'))
        kwargs.setdefault('subtypes', {'Vampire', 'Rogue'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'At the beginning of your end step, if an opponent lost life this turn, put a +1/+1 counter on target Vampire you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register end step trigger for Vampire counter."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _an_opponent_lost_life(game: 'GameState', ctrl: Any) -> bool:
            return any(getattr(player, 'life_lost_this_turn', 0) > 0 for player in game.players if player is not ctrl)

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, 'controller', None)
            return ctrl is not None and game.active_player is ctrl and _an_opponent_lost_life(game, ctrl)

        def _targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any] | None:
            def _vampire_you_control(obj: Any) -> bool:
                return (CardType.CREATURE in getattr(obj, 'card_types', set()) and 'Vampire' in getattr(obj, 'subtypes', set())
                        and getattr(obj, 'controller', None) is ctrl)

            return choose_trigger_targets(game, ctrl, source, [TargetRequirement(
                filter_fn=_vampire_you_control, description='Choose a Vampire to put a +1/+1 counter on',
                zone=Zone.BATTLEFIELD)])

        def _effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            # Intervening "if" (rule 603.4), for the controller the ability had
            # when it triggered, whoever controls its source now.
            if not _an_opponent_lost_life(game, context.controller):
                return
            (target,) = targets
            if target is not None:
                add_counter(game, target, '+1/+1', 1)
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, targeting=_targeting, printed=StromkirkBloodthiefAbility1))
