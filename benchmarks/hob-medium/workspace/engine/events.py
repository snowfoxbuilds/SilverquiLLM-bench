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

from dataclasses import dataclass, field
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
    counter_type: Any = None


@dataclass
class EntersBattlefieldReplacementEvent(ReplacementEvent):
    """A permanent about to enter the battlefield (rule 614.1c).

    Consulted **before** the permanent is placed, so "enters with N counters"
    replacements land the counters AS the permanent enters — it never exists at
    0/0 and never dies to the 0-toughness state-based action.

    ``counters`` maps ``counter_type -> amount`` and is populated by two
    channels, both while the entering permanent is still off the battlefield:

    * the entering card's own ``enters_battlefield_with(game, event)`` self-hook
      (its registry effects are not yet registered at this point, so the hook is
      called directly on the object); and
    * third-party replacement effects registered on this event type — e.g.
      *Giada, Font of Hope* granting each other Angel an extra +1/+1 counter for
      each Angel already controlled.

    The engine then lands ``counters`` through the shared counter helper (so
    *Doubling Season* et al. still double them via ``AddCounterReplacementEvent``)
    after placement but before the ETB event and the first SBA pass, and fires
    one ``CounterAddedTriggeredEvent`` per counter type afterward.
    """

    permanent: Any = None
    controller: Any = None
    from_zone: Any = None
    counters: dict = field(default_factory=dict)
