"""Card implementation for Battlesong Berserker."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer, SubLayer
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BattlesongBerserkerAbility1:
    text = "Whenever you attack, target creature you control gets +1/+0 and gains menace until end of turn. (It can't be blocked except by two or more creatures.)"


# endregion Printed abilities


class BattlesongBerserker(Creature):
    """Battlesong Berserker — {3}{R} — 3/4 — Human Berserker.

    Whenever you attack, target creature you control gets +1/+0 and gains
    menace until end of turn.

    FDN collector number 78.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Battlesong Berserker')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{R}'))
        kwargs.setdefault('subtypes', {'Human', 'Berserker'})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Whenever you attack, target creature you control gets +1/+0 and gains menace until end of turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for +1/+0 and menace."""
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            attacker = event.creature
            ctrl = getattr(source, 'controller', None)
            return getattr(attacker, 'controller', None) is ctrl and ctrl is not None

        def _targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any] | None:
            return choose_trigger_targets(game, ctrl, source, [TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, 'card_types', set()) and getattr(obj, 'controller', None) is ctrl,
                description='creature to get +1/+0 and menace', zone=Zone.BATTLEFIELD)])

        def _effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            (chosen,) = stint_checked_targets(game, context, targets)
            if chosen is None or getattr(chosen, 'controller', None) is not context.controller:
                return

            def _apply(game: Any) -> None:
                chosen.modified_power += 1
                chosen.keywords = (getattr(chosen, 'keywords', None) or Keyword(0)) | Keyword.MENACE
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, bound_to=[chosen], apply=_apply, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, targeting=_targeting, printed=BattlesongBerserkerAbility1))
