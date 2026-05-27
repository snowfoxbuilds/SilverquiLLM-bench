"""Typed event objects for triggered abilities and replacement effects.

Triggered events are passed to :meth:`TriggerManager.fire_event` and
forwarded to trigger condition callables.

Replacement events are passed to :meth:`ReplacementManager.apply` and
forwarded to replacement condition/replacement callables.  Subclassing
encodes event-type hierarchy so a replacement registered for a parent
type (e.g. ``MoveToGraveyardReplacementEvent``) also fires for
subtypes (e.g. ``CreatureDiesReplacementEvent``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Triggered events
# ---------------------------------------------------------------------------

@dataclass
class TriggeredEvent:
    """Base class for all triggered-ability events."""


@dataclass
class EntersBattlefieldTriggeredEvent(TriggeredEvent):
    permanent: Any = None
    controller: Any = None
    card: Any = None
    creature: Any = None


@dataclass
class LeavesBattlefieldTriggeredEvent(TriggeredEvent):
    permanent: Any = None
    controller: Any = None


@dataclass
class DealsDamageTriggeredEvent(TriggeredEvent):
    source: Any = None
    target: Any = None
    amount: int = 0
    is_combat: bool = False
    combat: bool = False


@dataclass
class LosesLifeTriggeredEvent(TriggeredEvent):
    player: Any = None
    amount: int = 0


@dataclass
class GainsLifeTriggeredEvent(TriggeredEvent):
    player: Any = None
    amount: int = 0


@dataclass
class DrawsCardTriggeredEvent(TriggeredEvent):
    player: Any = None
    card: Any = None


@dataclass
class BeginningOfUpkeepTriggeredEvent(TriggeredEvent):
    pass


@dataclass
class BeginningOfCombatTriggeredEvent(TriggeredEvent):
    pass


@dataclass
class EndOfTurnTriggeredEvent(TriggeredEvent):
    pass


@dataclass
class EndStepTriggeredEvent(TriggeredEvent):
    player: Any = None


@dataclass
class CreatureDiesTriggeredEvent(TriggeredEvent):
    creature: Any = None
    controller: Any = None
    owner: Any = None


@dataclass
class SpellCastTriggeredEvent(TriggeredEvent):
    spell: Any = None
    player: Any = None
    card: Any = None
    controller: Any = None


@dataclass
class AttacksTriggeredEvent(TriggeredEvent):
    creature: Any = None
    attacker: Any = None


@dataclass
class BlocksTriggeredEvent(TriggeredEvent):
    creature: Any = None


@dataclass
class CounterAddedTriggeredEvent(TriggeredEvent):
    permanent: Any = None
    counter_type: Any = None
    amount: int = 0


@dataclass
class BeginningOfMainPhaseEvent(TriggeredEvent):
    """Fired at the beginning of a player's first main phase."""
    player: Any = None


# ---------------------------------------------------------------------------
# Replacement events
# ---------------------------------------------------------------------------

@dataclass
class ReplacementEvent:
    """Base class for all replacement-effect events."""


@dataclass
class MoveToGraveyardReplacementEvent(ReplacementEvent):
    """Any permanent moving to a graveyard.

    Subclass this for specific causes (destruction, sacrifice, etc.).
    A replacement registered for this type also fires for all subtypes.

    ``destination`` may be mutated by a replacement to redirect the
    permanent to a different zone (``"exile"``, ``"library"``, ``"hand"``).
    Set ``prevented = True`` to signal that the replacement handled the
    zone move itself and the engine should skip its own move.
    """

    destination: str = "graveyard"
    controller: Any = None
    owner: Any = None
    prevented: bool = False

    @property
    def card(self) -> Any:
        """The object moving to the graveyard (overridden by subclasses)."""
        return None


@dataclass
class CreatureDiesReplacementEvent(MoveToGraveyardReplacementEvent):
    """A creature going to the graveyard via destruction or lethal damage."""

    creature: Any = None

    @property
    def card(self) -> Any:
        return self.creature


@dataclass
class PermanentDestroyedReplacementEvent(MoveToGraveyardReplacementEvent):
    """A non-creature permanent going to the graveyard via destruction."""

    permanent: Any = None

    @property
    def card(self) -> Any:
        return self.permanent


@dataclass
class SacrificeReplacementEvent(MoveToGraveyardReplacementEvent):
    """A permanent going to the graveyard via sacrifice."""

    permanent: Any = None

    @property
    def card(self) -> Any:
        return self.permanent


@dataclass
class CreateTokenReplacementEvent(ReplacementEvent):
    """An effect about to create one or more tokens."""

    player: Any = None
    count: int = 1


@dataclass
class AddCounterReplacementEvent(ReplacementEvent):
    """An effect about to add one or more counters to a permanent."""

    permanent: Any = None
    amount: int = 1
