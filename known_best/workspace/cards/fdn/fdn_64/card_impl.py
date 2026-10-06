"""Card implementation for Infestation Sage."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from cards.fdn.tokens import make_creature_token
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype, Zone
from engine.events import CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class InfestationSageAbility1:
    text = 'When this creature dies, create a 1/1 black and green Insect creature token with flying.'


# endregion Printed abilities


def _self_dies_condition(source: Any):
    """Return a condition callable that matches only when *source* dies."""

    def _condition(game: Any, event: dict) -> bool:
        return event.creature is source
    return _condition

class InfestationSage(Creature):
    """Infestation Sage — {B} — 1/1 — Elf Warlock

    When this creature dies, create a 1/1 black and green Insect creature
    token with flying.

    FDN collector number 64.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Infestation Sage')
        kwargs.setdefault('mana_cost', ManaCost.parse('{B}'))
        kwargs.setdefault('subtypes', {'Elf', 'Warlock'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'When this creature dies, create a 1/1 black and green Insect creature token with flying.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        from engine.game import create_token

        def _effect(game: GameState, controller: Any) -> None:
            # The fire-time controller: as the source last existed if it died
            # (rules 603.3a, 603.10a).
            if controller is None:
                return
            token = make_creature_token("Insect", {"Insect"}, [Color.BLACK, Color.GREEN], 1, 1, keywords=Keyword.FLYING)
            create_token(game, controller, token)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_self_dies_condition(self), effect=_effect, source=self, controller=controller, printed=InfestationSageAbility1))
