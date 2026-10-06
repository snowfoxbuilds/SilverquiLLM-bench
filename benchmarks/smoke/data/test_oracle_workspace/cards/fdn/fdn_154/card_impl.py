"""Card implementation for Extravagant Replication."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ExtravagantReplicationAbility1:
    text = "At the beginning of your upkeep, create a token that's a copy of another target nonland permanent you control."


# endregion Printed abilities


class ExtravagantReplication(Enchantment):
    """Extravagant Replication — {4}{U}{U} — Enchantment.

    At the beginning of your upkeep, create a token that's a copy of
    another target nonland permanent you control.

    FDN collector number 154.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Extravagant Replication')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{U}{U}'))
        kwargs.setdefault('rules_text', "At the beginning of your upkeep, create a token that's a copy of another target nonland permanent you control.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register upkeep trigger to copy a nonland permanent."""
        from engine.game import create_token, mint_token_copy
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            return game.active_player is ctrl

        def _targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any] | None:
            def _another_nonland_you_control(obj: Any) -> bool:
                return (obj is not source and CardType.LAND not in getattr(obj, 'card_types', set())
                        and getattr(obj, 'controller', None) is ctrl)

            return choose_trigger_targets(game, ctrl, source, [TargetRequirement(
                filter_fn=_another_nonland_you_control, description='Choose a nonland permanent to copy',
                zone=Zone.BATTLEFIELD)])

        def _effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            (chosen,) = stint_checked_targets(game, context, targets)
            if chosen is None or getattr(chosen, 'controller', None) is not context.controller:
                return
            # A token copy is a new object with only the copiable characteristics
            # (rule 707.2): mint_token_copy re-mints identity and drops the
            # original's counters/damage/tap, unlike a bare copy.copy.
            create_token(game, context.controller, mint_token_copy(chosen))
        game.trigger_manager.register(TriggerRegistration(event_type=BeginningOfUpkeepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, targeting=_targeting, printed=ExtravagantReplicationAbility1))
