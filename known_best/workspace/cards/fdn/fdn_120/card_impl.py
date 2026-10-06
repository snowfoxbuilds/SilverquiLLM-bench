"""Card implementation for Fiendish Panda."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import CreatureDiesTriggeredEvent, GainsLifeTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class FiendishPandaAbility1:
    text = 'Whenever you gain life, put a +1/+1 counter on this creature.'


class FiendishPandaAbility2:
    text = "When this creature dies, return another target non-Bear creature card with mana value less than or equal to this creature's power from your graveyard to the battlefield."


# endregion Printed abilities


def _self_dies_condition(source: Any):
    """Return a condition callable that matches only when *source* dies."""

    def _condition(game: Any, event: dict) -> bool:
        return event.creature is source
    return _condition

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class FiendishPanda(Creature):
    """Fiendish Panda — {2}{W}{B} — 3/2 — Bear Demon

    Whenever you gain life, put a +1/+1 counter on this creature.
    When this creature dies, return another target non-Bear creature card
    with mana value less than or equal to this creature's power from your
    graveyard to the battlefield.

    FDN collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Fiendish Panda')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{W}{B}'))
        kwargs.setdefault('subtypes', {'Bear', 'Demon'})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', "Whenever you gain life, put a +1/+1 counter on this creature.\nWhen this creature dies, return another target non-Bear creature card with mana value less than or equal to this creature's power from your graveyard to the battlefield.")
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.game import add_counter
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        from engine.zones import move_to_zone
        source = self

        def _lifegain_condition(game: Any, event: dict) -> bool:
            player = event.player
            controller = getattr(source, 'controller', None)
            return player is controller

        def _lifegain_effect(game: GameState) -> None:
            if _is_on_battlefield(game, source):
                add_counter(game, source, '+1/+1', 1)

        def _dies_targeting(game: Any, event: Any, controller: Any) -> list[Any] | None:
            # "this creature's power" as it last existed (rule 603.10a); the
            # target is chosen as the trigger goes on the stack (rule 603.3d).
            power = event.last_known.power

            def _returnable(obj: Any) -> bool:
                mana_cost = getattr(obj, 'mana_cost', None)
                return (obj is not source and controller.zones[Zone.GRAVEYARD].contains(obj)
                        and CardType.CREATURE in getattr(obj, 'card_types', set())
                        and 'Bear' not in getattr(obj, 'subtypes', set())
                        and (mana_cost is None or mana_cost.cmc <= power))

            return choose_trigger_targets(game, controller, source, [TargetRequirement(
                filter_fn=_returnable, description='another target non-Bear creature card to return',
                zone=Zone.GRAVEYARD)])

        def _dies_effect(game: GameState, targets: list[Any], context: Any) -> None:
            (target,) = stint_checked_targets(game, context, targets)
            if target is None:
                return
            target.controller = context.controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=GainsLifeTriggeredEvent, condition=_lifegain_condition, effect=_lifegain_effect, source=self, controller=controller, printed=FiendishPandaAbility1))
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_self_dies_condition(self), effect=_dies_effect, source=self, controller=controller, targeting=_dies_targeting, printed=FiendishPandaAbility2))
