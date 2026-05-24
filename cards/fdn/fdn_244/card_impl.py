"""Card implementation for Progenitus."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.protection import ProtectionAbility
from benchmarks.sos.workspace.engine.events import MoveToGraveyardReplacementEvent
from benchmarks.sos.workspace.engine.replacement_effects import ReplacementEffect
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class Progenitus(Creature):
    """Progenitus — {W}{W}{U}{U}{B}{B}{R}{R}{G}{G} — 10/10 — Legendary Hydra Avatar.

    Protection from everything.
    If Progenitus would be put into a graveyard from anywhere, reveal
    Progenitus and shuffle it into its owner's library instead.

    FDN collector number 244.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Progenitus')
        kwargs.setdefault('mana_cost', ManaCost.parse('{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}'))
        kwargs.setdefault('subtypes', {'Hydra', 'Avatar'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('base_power', 10)
        kwargs.setdefault('base_toughness', 10)
        kwargs.setdefault('rules_text', "Protection from everything\nIf Progenitus would be put into a graveyard from anywhere, reveal Progenitus and shuffle it into its owner's library instead.")
        super().__init__(**kwargs)
        self._init_protection()

    def _init_protection(self) -> None:
        """Set up protection from everything. Called from __init__ and
        can be re-invoked after characteristic resets."""
        self.protections = [ProtectionAbility(quality='everything', predicate=lambda source: True)]

    def _reset_characteristics(self) -> None:
        """Override to reapply protection from everything after reset."""
        super()._reset_characteristics()
        self._init_protection()

    def register_replacement_effects(self, game: 'GameState') -> None:
        """Register graveyard-shuffle replacement effect.

        Registers a single :class:`~engine.events.MoveToGraveyardReplacementEvent`
        handler; the engine's zone-move pipeline dispatches subclass events
        (creature_dies, sacrifice, etc.) to this parent-type handler automatically.
        """
        source = self

        def _condition(game: Any, event: dict) -> bool:
            return event.card is source

        def _replacement(game: Any, event: dict) -> dict:
            owner = getattr(source, 'owner', None)
            if owner is not None:
                library = owner.zones[Zone.LIBRARY]
                library.add(source)
                library.shuffle()
            event.prevented = True
            return event
        controller = getattr(self, 'controller', None)
        game.replacement_manager.register(ReplacementEffect(event_type=MoveToGraveyardReplacementEvent, source=self, condition=_condition, replacement=_replacement, controller=controller))
