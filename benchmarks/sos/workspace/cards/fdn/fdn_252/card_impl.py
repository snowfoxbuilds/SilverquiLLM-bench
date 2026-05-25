"""Card implementation for Gleaming Barrier."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _self_dies_condition(source: Any):
    """Return a condition callable that matches only when *source* dies."""

    def _condition(game: Any, event: dict) -> bool:
        return event.creature is source
    return _condition

class GleamingBarrier(ArtifactCreature):
    """Gleaming Barrier — {2} — 0/4 — Wall — Defender

    When this creature dies, create a Treasure token.

    FDN collector number 252.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Gleaming Barrier')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}'))
        kwargs.setdefault('subtypes', {'Wall'})
        kwargs.setdefault('keywords', Keyword.DEFENDER)
        kwargs.setdefault('base_power', 0)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Defender\nWhen this creature dies, create a Treasure token.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.game import create_token
        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, 'controller', None) or getattr(source, 'owner', None)
            if controller is None:
                return
            from benchmarks.sos.workspace.engine.card import Artifact
            token = Artifact(name='Treasure', subtypes={'Treasure'})
            create_token(game, controller, token)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_self_dies_condition(self), effect=_effect, source=self, controller=controller))
