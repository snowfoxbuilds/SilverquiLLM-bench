"""Player interface for the MSH Player Query protocol.

The ``Player`` ABC exposes a single entry point — ``answer(query) -> Answer`` —
the engine's native interaction surface for the *choice* layer. There is no V1
``choose_*`` surface and no ``ScriptExhaustedError``: an answer that no offered
option satisfies is a test-authoring failure (``IntentError`` family), and a
malformed/unanswerable query is an engine failure (``ProtocolError`` family).

The concrete intent-based ``DeterministicPlayer`` lives in
``engine/intent_player.py`` (and is re-exported from ``engine/__init__.py``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.mana import ManaPool
from engine.queries import Answer, PlayerQuery
from engine.zones import Zones


class Player(ABC):
    """Abstract base class for all players in the game.

    Attributes:
        name: The player's display name.
        life: Current life total (default 20).
        zones: Per-player zone containers.
        mana_pool: The player's mana pool.
        has_lost: Whether this player has lost the game.
        land_plays_remaining: Number of land plays remaining this turn.
        drawn_from_empty_library: Whether this player attempted to draw from an
            empty library.
    """

    def __init__(self, name: str, life: int = 20) -> None:
        self.name: str = name
        self.life: int = life
        self.zones: Zones = Zones.new_player()
        self.mana_pool: ManaPool = ManaPool()
        self.has_lost: bool = False
        self.land_plays_remaining: int = 1
        self.drawn_from_empty_library: bool = False

    @abstractmethod
    def answer(self, query: PlayerQuery) -> Answer:
        """Answer a Player Query.

        Parameters:
            query: The Player Query raised by the engine (already
                boundary-validated). Its ``options`` are the legal choices in
                implementation-provided stable order; ``min``/``max`` bound the
                selection; ``min == 0`` means legally declinable.

        Returns:
            An :class:`~engine.queries.Answer` whose ``selected`` is between
            ``min`` and ``max`` of the offered options (``Answer(())`` to
            decline when ``min == 0``). The engine validates the answer before
            applying it.
        """
