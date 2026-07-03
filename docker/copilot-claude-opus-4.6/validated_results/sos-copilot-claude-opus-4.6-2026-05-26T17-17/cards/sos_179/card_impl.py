"""Card implementation for Cauldron of Essence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Artifact, Creature
from engine.types import ManaCost, ManaType, CardType, Zone
from engine.events import CreatureDiesTriggeredEvent

if TYPE_CHECKING:
    from engine.game_state import GameState


class CauldronOfEssence(Artifact):
    """Cauldron of Essence — {1}{B}{G} — Artifact.

    Whenever a creature you control dies, each opponent loses 1 life and
    you gain 1 life.

    {1}{B}{G}, {T}, Sacrifice a creature: Return target creature card from
    your graveyard to the battlefield. Activate only as a sorcery.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Cauldron of Essence')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{G}'))
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            # Only trigger for creatures controlled by the same player
            creature_ctrl = getattr(event, 'controller', None)
            return creature_ctrl is ctrl

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            # Each opponent loses 1 life
            for p in game.players:
                if p is not ctrl:
                    p.life -= 1
            # Controller gains 1 life
            ctrl.life += 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=CreatureDiesTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def activate(self, game: 'GameState', sacrifice: Any = None, target: Any = None) -> None:
        """Activate: {1}{B}{G}, {T}, Sacrifice a creature: Return target creature from graveyard."""
        controller = getattr(self, 'controller', None) or getattr(self, 'owner', None)
        if controller is None:
            return

        # Tap the cauldron
        self.is_tapped = True

        # Sacrifice the creature
        if sacrifice is not None:
            bf = game.get_battlefield(controller)
            if bf.contains(sacrifice):
                bf.remove(sacrifice)
                game.get_graveyard(controller).add(sacrifice)

        # Return target creature from graveyard to battlefield
        if target is not None:
            gy = game.get_graveyard(controller)
            if gy.contains(target):
                gy.remove(target)
                bf = game.get_battlefield(controller)
                bf.add(target)
                target.controller = controller
