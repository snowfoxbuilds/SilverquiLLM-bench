"""Card implementation for Alesha, Who Laughs at Fate."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, EndStepTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class AleshaWhoLaughsAtFateAbility1:
    text = 'First strike'


class AleshaWhoLaughsAtFateAbility2:
    text = 'Whenever Alesha attacks, put a +1/+1 counter on it.'


class AleshaWhoLaughsAtFateAbility3:
    text = "Raid — At the beginning of your end step, if you attacked this turn, return target creature card with mana value less than or equal to Alesha's power from your graveyard to the battlefield."


# endregion Printed abilities


class AleshaWhoLaughsAtFate(Creature):
    """Alesha, Who Laughs at Fate — {1}{B}{R} — 2/2 — Legendary Human Warrior.

    First strike
    Whenever Alesha attacks, put a +1/+1 counter on it.
    Raid — At the beginning of your end step, if you attacked this turn,
    return target creature card with mana value less than or equal to
    Alesha's power from your graveyard to the battlefield.

    FDN collector number 115.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Alesha, Who Laughs at Fate')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{R}'))
        kwargs.setdefault('subtypes', {'Human', 'Warrior'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('keywords', Keyword.FIRST_STRIKE)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', "First strike\nWhenever Alesha attacks, put a +1/+1 counter on it.\nRaid — At the beginning of your end step, if you attacked this turn, return target creature card with mana value less than or equal to Alesha's power from your graveyard to the battlefield.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger and Raid end-step trigger."""
        from engine.game import add_counter
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        from engine.zones import move_to_zone
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _attack_condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _attack_effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1')
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller, printed=AleshaWhoLaughsAtFateAbility2))

        def _raid_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            attacked = getattr(game, 'attacked_this_turn', False)
            if not attacked:
                attacked = getattr(ctrl, 'attacked_this_turn', False)
            return attacked

        def _returnable(ctrl: Any, power: int) -> Any:
            def _legal(obj: Any) -> bool:
                mana_cost = getattr(obj, 'mana_cost', None)
                return (ctrl.zones[Zone.GRAVEYARD].contains(obj) and CardType.CREATURE in getattr(obj, 'card_types', set())
                        and mana_cost is not None and mana_cost.cmc <= power)
            return _legal

        def _raid_targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any] | None:
            return choose_trigger_targets(game, ctrl, source, [TargetRequirement(
                filter_fn=_returnable(ctrl, source.power), description='creature card to return from graveyard',
                zone=Zone.GRAVEYARD)])

        def _raid_effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            from engine.last_known import as_it_exists
            ctrl = context.controller
            # "Alesha's power": current while it remains on the battlefield,
            # otherwise as it last existed there (rule 608.2h).
            alesha = as_it_exists(game, source, context.source_instance_id)
            power = alesha.power if alesha is not None else 0
            (chosen,) = stint_checked_targets(game, context, targets)
            if chosen is None or not _returnable(ctrl, power)(chosen):
                return
            chosen.controller = ctrl
            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_raid_condition, effect=_raid_effect, source=self, controller=controller, targeting=_raid_targeting, printed=AleshaWhoLaughsAtFateAbility3))
