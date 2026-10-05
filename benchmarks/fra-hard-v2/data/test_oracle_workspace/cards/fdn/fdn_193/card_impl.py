"""Card implementation for Drakuseth, Maw of Flames."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class DrakusethMawOfFlamesAbility1:
    text = 'Flying'


class DrakusethMawOfFlamesAbility2:
    text = 'Whenever Drakuseth attacks, it deals 4 damage to any target and 3 damage to each of up to two other targets.'


# endregion Printed abilities


class DrakusethMawOfFlames(Creature):
    """Drakuseth, Maw of Flames — {4}{R}{R}{R} — 7/7 — Legendary Dragon.

    Flying.
    Whenever Drakuseth attacks, it deals 4 damage to any target and 3
    damage to each of up to two other targets.

    FDN collector number 193.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Drakuseth, Maw of Flames')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{R}{R}{R}'))
        kwargs.setdefault('subtypes', {'Dragon'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 7)
        kwargs.setdefault('base_toughness', 7)
        kwargs.setdefault('rules_text', 'Flying\nWhenever Drakuseth attacks, it deals 4 damage to any target and 3 damage to each of up to two other targets.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for damage dealing."""
        from engine.game import deal_damage
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _any_target(obj: Any, chosen: Any = ()) -> bool:
            if any(obj is p for p in game.players):
                return True
            types = getattr(obj, 'card_types', set())
            return CardType.CREATURE in types or CardType.PLANESWALKER in types

        def _targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any] | None:
            # Chosen as the trigger goes on the stack (rule 603.3d): one target
            # for 4 damage, then up to two other targets for 3 each.
            return choose_trigger_targets(game, ctrl, source, [
                TargetRequirement(filter_fn=_any_target, description='Choose a target for 4 damage', zone=Zone.BATTLEFIELD),
                TargetRequirement(filter_fn=_any_target, description='Choose target 1 for 3 damage (optional)', zone=Zone.BATTLEFIELD, optional=True),
                TargetRequirement(filter_fn=_any_target, description='Choose target 2 for 3 damage (optional)', zone=Zone.BATTLEFIELD, optional=True),
            ])

        def _effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            for i, target in enumerate(stint_checked_targets(game, context, targets)):
                if target is not None:
                    deal_damage(game, source, target, 4 if i == 0 else 3)
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, targeting=_targeting, printed=DrakusethMawOfFlamesAbility2))
