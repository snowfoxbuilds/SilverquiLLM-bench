"""Card implementation for Bogwater Lumaret."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost, CardType
from engine.events import EntersBattlefieldTriggeredEvent

if TYPE_CHECKING:
    from engine.game_state import GameState


class BogwaterLumaret(Creature):
    """Bogwater Lumaret — {B}{G} — 2/2 — Spirit Frog.

    Whenever this creature or another creature you control enters, you gain 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Bogwater Lumaret')
        kwargs.setdefault('mana_cost', ManaCost.parse('{B}{G}'))
        kwargs.setdefault('subtypes', {'Spirit', 'Frog'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
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
            perm = event.permanent
            if perm is None:
                return False
            perm_ctrl = getattr(perm, 'controller', None)
            if perm_ctrl is not ctrl:
                return False
            # Must be a creature
            card_types = getattr(perm, 'card_types', set())
            return CardType.CREATURE in card_types

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            ctrl.life += 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

        # Self-ETB: In MTG, "Whenever this or another creature enters" triggers
        # on its own entry. The engine fires ETB before registering triggers,
        # so we compensate here only if entering from the stack (casting).
        # Detect this by checking if we were just on the stack (cast flow).
        if getattr(source, '_entering_from_cast', False):
            source._entering_from_cast = False
            if controller is not None:
                controller.life += 1

    def on_cast(self, game: 'GameState') -> None:
        """Mark that this card is being cast (for self-ETB detection)."""
        self._entering_from_cast = True
