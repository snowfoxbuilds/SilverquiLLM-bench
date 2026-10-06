"""Player interface for the V2 Player Query protocol.

The ``Player`` ABC exposes a single entry point — ``answer(query) -> Answer`` —
the engine's native interaction surface for the *choice* layer. There is no V1
``choose_*`` surface and no ``ScriptExhaustedError``: an answer that no offered
option satisfies is a test-authoring failure (``IntentError`` family), and a
malformed/unanswerable query is an engine failure (``ProtocolError`` family).

The players that answer from a test's scripts belong to the tests: the Test
Interface's ``ScriptedPlayer`` and ``test_utils``' ``DeterministicPlayer``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from engine.decisions import InvalidPlayerChoiceError
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
        # Whether this player declared an attacker this turn (rule 508.1);
        # cleared at each turn boundary.
        self.attacked_this_turn: bool = False
        # Authoritative per-turn record of the instant and sorcery spells THIS
        # player has cast this turn (rule "…instant and sorcery spell you've cast
        # … this turn", e.g. Thousand-Year Storm's copy count). This belongs to
        # the player/turn lifecycle, not to any one triggered-ability source: it
        # counts qualifying spells whether or not such a source is present, is
        # recorded exactly once at the single authoritative cast site
        # (:func:`engine.casting.cast_spell` / ``cast_spell_free``) — never by a
        # trigger's capture hook, so multiple observers cannot inflate it — and is
        # turn-stamped so it resets lazily at the turn boundary (a stale stamp
        # reads as an empty record).
        #
        # Each entry is a *cast occurrence*, not a permanent handle on a card:
        # casting the same physical ``CardImpl`` object twice this turn appends
        # two entries. The number of qualifying casts *before* a given occurrence
        # is fixed the moment that occurrence is recorded (its position in the
        # list at append time) and returned by
        # :meth:`record_instant_or_sorcery_cast` — so a consumer never has to
        # exclude "the current cast" by object identity (which would wrongly drop
        # *every* earlier occurrence of a recast object). See
        # :meth:`record_instant_or_sorcery_cast`.
        self._instant_sorcery_casts: list[Any] = []
        self._instant_sorcery_cast_turn: int | None = None

    # ------------------------------------------------------------------
    # Instant/sorcery cast history (per-turn, authoritative)
    # ------------------------------------------------------------------

    def record_instant_or_sorcery_cast(self, spell: Any, turn_number: int) -> int:
        """Record that this player cast instant/sorcery *spell* on *turn_number*.

        Turn-stamped: the first cast recorded on a new turn number resets the
        record before appending, so a prior turn's casts never carry over (the
        turn boundary reset happens exactly once, lazily, without relying on any
        cleanup step running). Called exactly once per cast from the casting
        pipeline; the caller filters to instant/sorcery spells.

        Returns the number of qualifying casts this player had already made this
        turn *before* this one — i.e. the count of "other instant and sorcery
        spells you've cast before it this turn". This is the immutable prior-cast
        count for this exact occurrence, fixed at record time as its position in
        the per-turn list. Because it is captured before the current cast is
        counted, a consumer excludes exactly this occurrence — never every
        earlier occurrence of a recast object, and never by fragile object
        identity. The casting pipeline carries this value onto the cast's
        :class:`~engine.stack.StackObject`, the stack representation of this one
        occurrence.
        """
        if self._instant_sorcery_cast_turn != turn_number:
            self._instant_sorcery_cast_turn = turn_number
            self._instant_sorcery_casts = []
        prior_qualifying_casts = len(self._instant_sorcery_casts)
        self._instant_sorcery_casts.append(spell)
        return prior_qualifying_casts

    def instant_or_sorcery_casts_this_turn(self, turn_number: int) -> list[Any]:
        """Return the instant/sorcery spells this player has cast on *turn_number*.

        A copy of the record, in cast order, or an empty list when the recorded
        turn stamp is stale (a prior turn's casts do not contribute this turn).
        Each element is one cast occurrence, so a physical card object cast
        several times this turn appears several times, once per cast.
        """
        if self._instant_sorcery_cast_turn != turn_number:
            return []
        return list(self._instant_sorcery_casts)

    # Decision-side attributes a rejected action's rollback leaves alone
    # (engine.rollback): what the player saw and chose is not game state.
    rollback_exempt: frozenset[str] = frozenset()

    def on_attempt_rejected(self, context: Any, answer: Any, error: InvalidPlayerChoiceError) -> None:
        """Hear that a rejection belongs to ``answer``, one this player gave
        during ``context`` (an :class:`~engine.attempts.AttemptContext`, which
        names the attempt, the action it belongs to and that action's player),
        after the game was rolled back (see ADR-017).

        Returning lets the engine ask the same query again (CR 733.2), and the
        player must then answer it differently; raising stops play with an
        error. The default raises ``error``, so a player that cannot revise
        its choice is never asked forever.

        The game is rolled back again after this hook returns, so state the
        player keeps for its decisions must be listed in ``rollback_exempt``.
        """
        raise error

    def on_action_ended(self, context: Any) -> None:
        """Hear that the priority action or declaration attempted in
        ``context`` is over — taken, passed, or ended by an error — so nothing
        of it should answer later queries. The default does nothing."""

    def confirm_declaration(
        self, query: PlayerQuery, answer: Answer, outcome: tuple[Any, ...] = ()
    ) -> None:
        """Hear that the combat declaration chosen in ``answer`` to ``query``
        has had every question answered and is about to take effect.
        ``outcome`` pairs each declared creature's option with the decisions
        for what it attacks or blocks — the declaration as it will stand,
        whichever follow-up questions the engine asked.

        Raising ``InvalidPlayerChoiceError`` withdraws it: it is rolled back
        like a rejected declaration, before any combat state is committed, and
        the same declaration is asked again. The default does nothing."""

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
