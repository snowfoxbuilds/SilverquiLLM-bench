"""Replay executor with state-diff observer mode.

Steps through GameSnapshot objects from the parser and validates engine
behavior using state-diff comparison. Seat 1 (17lands user) gets full
validation; Seat 2 (opponent) uses oracle injection.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from silverquillm.replay.types import (
    GameSnapshot,
    GameObject,
    ReplayAction,
    ReplayGame,
    TurnInfo,
)

logger = logging.getLogger(__name__)


def _make_replay_player(name: str, life: int) -> Any:
    """Create a DeterministicPlayer for whichever workspace engine is on sys.path.

    Benchmark-parameterized: the frozen SOS (V1) engine has a scripted
    ``engine.player.DeterministicPlayer`` (replay drives its actions, not a
    script); the MSH engine has the intent-based ``engine.intent_player.
    DeterministicPlayer``, which gets a permissive Baseline Intent so any query
    the replay raises is answered in GRE-observed (first-offered) order rather
    than crashing. A genuinely unanswerable query surfaces as a
    ``QUERY_UNANSWERED`` divergence, not an exception.
    """
    try:
        from engine.intent_player import DeterministicPlayer as _IntentPlayer
        from engine.intent_player import Intent
        from engine.decisions import GameRef

        player = _IntentPlayer(name=name, life=life)
        player.set_baseline(Intent(pattern=GameRef(), preferences=()))
        return player
    except ImportError:
        # Frozen SOS engine — V1 scripted player (replay drives actions).
        from engine.player import DeterministicPlayer as _V1Player

        return _V1Player(name=name, script=[], life=life)


# ---------------------------------------------------------------------------
# State comparison result
# ---------------------------------------------------------------------------

@dataclass
class StateMismatch:
    """A single mismatch between engine state and GRE snapshot."""

    category: str  # "life_total", "zone_contents", "battlefield_state", "tapped_state", "power_toughness"
    description: str
    engine_value: Any = None
    snapshot_value: Any = None
    seat_id: int = 0

    def __str__(self) -> str:
        return f"[{self.category}] {self.description}: engine={self.engine_value}, snapshot={self.snapshot_value}"


@dataclass
class StepResult:
    """Result of processing one snapshot transition."""

    snapshot_id: int
    action_type: str = ""
    seat_id: int = 0
    card_name: str = ""
    success: bool = True
    mismatches: list[StateMismatch] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    # Simulate mode: engine API calls that failed and fell back to oracle
    # mutation. Each entry becomes an ENGINE_ERROR divergence — failures are
    # recorded, never masked.
    engine_failures: list[str] = field(default_factory=list)
    # Simulate mode: executor-side impossibilities (empty engine library on a
    # GRE-observed draw, step-event plumbing) — REPLAY_INFRA divergences,
    # kept out of the engine/card-bug signal.
    infra_failures: list[str] = field(default_factory=list)
    # Simulate mode: hidden-origin actions the executor synthesized for this
    # step (_infer_hidden_origin_actions) — exposed so validation can count
    # missing cards the parser's action stream never sees.
    synthesized_actions: list[ReplayAction] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        """True if no mismatches were found."""
        return len(self.mismatches) == 0


# ---------------------------------------------------------------------------
# Card ID map loader (reuses parser logic but provides a standalone path)
# ---------------------------------------------------------------------------

def load_card_id_map(path: str | Path | None = None) -> dict[int, str]:
    """Load grpId -> card name mapping from JSON file."""
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "replays" / "card_id_map.json"
    else:
        path = Path(path)

    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    result: dict[int, str] = {}
    for grp_id_str, info in data.get("grpId_to_card", {}).items():
        try:
            result[int(grp_id_str)] = info["card_name"]
        except (ValueError, KeyError):
            continue

    return result


# ---------------------------------------------------------------------------
# Token identity map (corpus-derived; see scripts/build_token_id_map.py)
# ---------------------------------------------------------------------------

def _token_signature(
    card_types: Any, subtypes: Any, power: Any, toughness: Any
) -> tuple:
    """The characteristic signature used to correlate engine tokens to GRE ones.

    ``card_types`` is normalized to lowercase type names ('creature',
    'artifact', ...), so an engine ``CardType.CREATURE`` and a GRE
    ``CardType_Creature`` produce the same key. Base P/T is part of the
    signature ONLY for creatures — it is what tells the two red Dragon tokens
    (94171 4/4 vs 94172 5/5) apart — and is ignored for noncreature tokens
    (Food, Treasure) whose subtype already identifies them.
    """
    cts = frozenset(str(t).lower() for t in (card_types or []))
    subs = frozenset(subtypes or [])
    if "creature" in cts:
        return (cts, subs, power, toughness)
    return (cts, subs, None, None)


def _color_key(colors: Any) -> frozenset:
    """Normalize a colour collection to a comparable key.

    Accepts either the engine's ``Color`` enum members (``get_colors`` returns a
    ``set[Color]``) or the token map's colour strings (``["Red", "White"]``) and
    returns a frozenset of upper-cased colour names, so an engine ``Color.RED``
    and a map ``"Red"`` compare equal. An empty collection yields the empty
    frozenset, which callers read as EXPLICIT colourlessness (the map's
    ``"colors": []``). The undeclared/UNKNOWN state never reaches this
    normalization: ``_engine_token_color_key`` returns ``None`` for an engine
    token with no authoritative colour source, before any key is built.
    """
    key = set()
    for c in colors or []:
        name = getattr(c, "name", None) or str(c)
        key.add(name.upper())
    return frozenset(key)


class TokenIdMap:
    """Corpus-derived token identity map (data/replays/token_id_map.json).

    Gives every observed token grpId a stable identity so the executor can
    correlate engine-minted tokens to their GRE grpId (stamping ``_grp_id``)
    instead of treating them as anonymous id-0 shells, and so the validator can
    surface a token that has no engine impl as a named missing identity rather
    than an anonymous ``grpId_<n>``. Also resolves the four Arena-only card
    grpIds Scryfall's arena_id feed omits.
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        data = data or {}
        self._tokens: dict[int, dict] = {}
        for k, v in data.get("tokens", {}).items():
            try:
                self._tokens[int(k)] = v
            except (ValueError, TypeError):
                continue
        self._arena: dict[int, dict] = {}
        for k, v in data.get("arena_only_cards", {}).items():
            try:
                self._arena[int(k)] = v
            except (ValueError, TypeError):
                continue
        # Precompute the COMPLETE set of grpIds sharing each runtime signature.
        # Ambiguity is a property of the whole map, not of whichever identities
        # a single snapshot happens to show — so correlation must decide "does
        # this signature collide?" against this map-wide index, never against
        # the grpIds present in one battlefield group.
        self._sig_to_grps: dict[tuple, set[int]] = {}
        for grp_id in self._tokens:
            sig = self.signature(grp_id)
            if sig is not None:
                self._sig_to_grps.setdefault(sig, set()).add(grp_id)

    def __len__(self) -> int:
        """Number of known token identities (0 for an empty/observer map)."""
        return len(self._tokens)

    def is_token(self, grp_id: int) -> bool:
        """True if *grp_id* is a known token identity."""
        return grp_id in self._tokens

    def known_grp_ids(self) -> list[int]:
        """Every known token grpId, sorted (for auditing map collisions)."""
        return sorted(self._tokens)

    def signature(self, grp_id: int) -> tuple | None:
        """Correlation signature for a known token grpId (None if unknown)."""
        entry = self._tokens.get(grp_id)
        if entry is None:
            return None
        return _token_signature(
            entry.get("card_types"),
            entry.get("subtypes"),
            entry.get("base_power"),
            entry.get("base_toughness"),
        )

    def signature_candidates(self, sig: tuple | None) -> set[int]:
        """Every known token grpId whose runtime signature equals *sig*.

        The COMPLETE collision set for a signature — the map-wide truth about
        how many distinct identities can carry it. Correlation uses this (never
        the count of identities present in one snapshot) to decide whether a
        signature is unique or colliding: a signature two grpIds share is
        ambiguous even in a snapshot that shows only one of them, so a lone
        colliding identity must still go through identity-evidence validation
        rather than the count-only path. Empty for an unknown signature.
        """
        if sig is None:
            return set()
        return set(self._sig_to_grps.get(sig, ()))

    def color_key(self, grp_id: int) -> frozenset | None:
        """Normalized colour key for a known token grpId (None if unknown).

        The corpus-derived colour (``["Red"]``, ``["Black"]``, ``[]`` for a
        colourless token) upper-cased into a frozenset, so it compares directly
        against an engine token's known colour key (``_engine_token_color_key``;
        an unknown colour is ``None`` and never compares equal, unlike
        ``get_colors``, which flattens unknown to empty). Colour is the identity
        discriminator that tells two same-signature token grpIds apart (e.g. the
        1/1 red Human copy 93797 from the 1/1 white Human 94158); it is NOT part
        of the base signature because a token impl that omits its colour must
        still correlate on the common (single-grpId) path.
        """
        entry = self._tokens.get(grp_id)
        if entry is None:
            return None
        return _color_key(entry.get("colors"))

    def label(self, grp_id: int) -> str | None:
        """Human-readable identity for a token grpId (None if unknown)."""
        entry = self._tokens.get(grp_id)
        return entry.get("label") if entry else None

    def token_name(self, grp_id: int) -> str | None:
        """The card name for a copy-token whose grpId is a real card, else None."""
        entry = self._tokens.get(grp_id)
        return entry.get("name") if entry else None

    def arena_card_names(self) -> dict[int, str]:
        """grpId -> registered card name for the resolvable Arena-only cards."""
        return {
            grp: entry["resolves_to"]
            for grp, entry in self._arena.items()
            if entry.get("resolves_to")
        }

    def arena_label(self, grp_id: int) -> str | None:
        """Named identity for an Arena-only card grpId (None if not one)."""
        entry = self._arena.get(grp_id)
        if entry is None:
            return None
        return entry.get("resolves_to") or entry.get("label")


def load_token_id_map(
    path: str | Path | None = None, *, required: bool = False
) -> TokenIdMap:
    """Load the corpus-derived token identity map from JSON.

    ``required=True`` (used by the simulate-mode verification path) makes
    missing or malformed data fail VISIBLY instead of degrading to an empty map:
    a silently-empty map would still run, but every token would mis-report as
    unproducible / anonymous, quietly inflating the divergence and MISSING_CARD
    metrics the run exists to measure. Regeneration stays documented and
    reproducible via ``scripts/build_token_id_map.py``.
    """
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "replays" / "token_id_map.json"
    else:
        path = Path(path)
    if not path.exists():
        if required:
            raise FileNotFoundError(
                f"token identity map not found at {path}; simulate-mode "
                f"validation requires it — regenerate with "
                f"scripts/build_token_id_map.py"
            )
        return TokenIdMap({})
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:  # ValueError covers JSONDecodeError
        if required:
            raise ValueError(
                f"token identity map at {path} is malformed ({exc}); "
                f"regenerate with scripts/build_token_id_map.py"
            ) from exc
        raise
    token_map = TokenIdMap(data)
    if required and len(token_map) == 0:
        raise ValueError(
            f"token identity map at {path} carries no token entries; "
            f"simulate-mode validation would silently mis-report token "
            f"producibility — regenerate with scripts/build_token_id_map.py"
        )
    return token_map


# ---------------------------------------------------------------------------
# GRE zone type → engine zone mapping
# ---------------------------------------------------------------------------

_GRE_ZONE_TO_ENGINE: dict[str, str] = {
    "ZoneType_Hand": "hand",
    "ZoneType_Library": "library",
    "ZoneType_Battlefield": "battlefield",
    "ZoneType_Graveyard": "graveyard",
    "ZoneType_Exile": "exile",
    "ZoneType_Stack": "stack",
}

# GRE zones with ownerSeatId == 0 are shared between both players; the engine
# models per-player zones instead. Shared battlefield objects route to their
# *controller's* engine zone; other shared zones (exile) route by owner.
_SHARED_ZONE_ROUTE_BY_CONTROLLER = {"ZoneType_Battlefield"}

# Forward-scan bound (in snapshots) for annotations Arena streams AFTER the
# event they describe (ManaPaid funding a cast, TargetSpec naming targets).
# Observed lag is 1-6 snapshots; 30 is a comfortable ceiling that keeps scans
# bounded. Exactness comes from filtering on the described object's instance
# id — never reused within a game — not from the bound itself.
_ANNOTATION_LOOKAHEAD = 30

# Forward-scan bound for observing blocker deaths after a damage step; a
# combat's deaths resolve within its own snapshots, well inside this window.
_DEATH_LOOKAHEAD = 12

# Arena CounterType enum -> engine counter name. Derived from the FDN corpus
# CounterAdded feasibility histogram (Phase F): enum 1 is by far the most common
# (751/883 annotations) and lands on the +1/+1 cards (Ajani's Pridemate,
# Skyknight Squire, Stromkirk Bloodthief, Wildwood Scourge, Scavenging Ooze);
# the named-counter enums were pinned by the single card that carries each
# (Drake Hatcher = incubation, Nine-Lives Familiar = revival, Ravenous Amulet =
# soul). An enum not in this map is stored under a namespaced fallback name so
# it round-trips through the engine counter system without colliding with a
# card's own counter name (it just won't satisfy a card-specific cost).
_GRE_COUNTER_TYPE_TO_NAME: dict[int, str] = {
    1: "+1/+1",
    200: "incubation",
    201: "revival",
    146: "soul",
}


def _gre_counter_name(counter_type: int | None) -> str | None:
    """Map an Arena CounterType enum to an engine counter name (or a fallback)."""
    if counter_type is None:
        return None
    name = _GRE_COUNTER_TYPE_TO_NAME.get(counter_type)
    if name is not None:
        return name
    return f"gre_counter_{counter_type}"


# Module-qualified names of the MSH protocol exceptions (engine/decisions.py),
# matched via MRO so this shared code imports no MSH-only classes — the same
# scheme as validation.classify_step_exception. Protocol exceptions surface
# per the engine's contract (PROTOCOL_ERROR / QUERY_UNANSWERED); only
# non-protocol exceptions may become per-action engine_failures records.
_PROTOCOL_EXC_QUALNAMES = {
    ("engine.decisions", "ProtocolError"),
    ("engine.decisions", "UnmatchedQueryError"),
}


def _is_protocol_exception(exc: BaseException) -> bool:
    """True for MSH Player Query protocol exceptions (and subclasses)."""
    mro_qualnames = {(cls.__module__, cls.__name__) for cls in type(exc).__mro__}
    return bool(mro_qualnames & _PROTOCOL_EXC_QUALNAMES)


class _OraclePTCorrectionSource:
    """Sentinel ``source`` for replay-owned oracle P/T corrections.

    Never a game object: ``EffectManager.get_effects_by_source`` matches by
    identity, so tagging corrections with this singleton lets the resync
    find (and revoke) exactly its own effects — card-owned effects and
    ``_remove_synced_card``'s per-card effect cleanup can never collide.
    """

    name = "ReplayOraclePTCorrection"


_ORACLE_PT_SOURCE = _OraclePTCorrectionSource()


# ---------------------------------------------------------------------------
# ReplayExecutor
# ---------------------------------------------------------------------------

class ReplayExecutor:
    """Steps through a ReplayGame and validates engine state against GRE snapshots.

    Parameters:
        replay: The parsed ReplayGame to execute.
        card_id_map: Mapping from grpId to card name.
        registry: Optional CardRegistry for creating card instances.
        strict: If True, raise on mismatches. If False, collect and continue.
    """

    def __init__(
        self,
        replay: ReplayGame,
        card_id_map: dict[int, str] | None = None,
        registry: Any | None = None,
        strict: bool = False,
        simulate: bool = False,
        token_map: TokenIdMap | None = None,
    ) -> None:
        self.replay = replay
        self.card_id_map = card_id_map or {}
        self.registry = registry
        self.strict = strict
        # Simulation mode: drive gameplay through the engine (casting, combat,
        # mana) and compare state BEFORE resyncing. Default (False) is the
        # original observer mode that oracle-syncs state before comparison.
        self.simulate = simulate
        # Corpus-derived token identity map (Phase E). Loaded only in simulate
        # mode (and defaulted to the committed map so directly-constructed
        # simulate executors correlate too); observer mode gets an empty map and
        # never touches any Phase E path, so it stays byte-for-byte unchanged.
        if token_map is not None:
            self.token_map = token_map
        elif simulate:
            # Simulate is the verification path: a missing/malformed map must
            # fail visibly, not silently validate against an empty map.
            self.token_map = load_token_id_map(required=True)
        else:
            self.token_map = TokenIdMap()

        # Engine state (initialized from first snapshot)
        self.game: Any | None = None
        self.players: dict[int, Any] = {}  # seat_id -> engine Player

        # Tracking: grpId instance -> engine card object
        self._engine_cards: dict[int, Any] = {}  # GRE instanceId -> engine card
        self._grp_to_name: dict[int, str] = dict(self.card_id_map)
        # Resolve the four Arena-only card grpIds Scryfall's arena_id feed omits
        # to their registered impl name, so the executor builds the real card
        # (Gnarlid Colony, Embercleave, Llanowar Elves) instead of a shell. Only
        # fills gaps — a real card_id_map entry always wins. Simulate-only (the
        # map is empty in observer mode, so this loop is a no-op there).
        for grp_id, name in self.token_map.arena_card_names().items():
            self._grp_to_name.setdefault(grp_id, name)

        # Tracks which engine cards have had register_triggers applied (prevents double-apply)
        self._triggers_registered: set[int] = set()

        # Token grpIds the engine actually minted and correlated this game (via
        # _correlate_tokens_in_group). The producibility signal for MISSING_CARD
        # semantics: a GRE token whose grpId is here was produced by a real
        # engine impl; one that never appears here has no impl that mints it and
        # must still surface as a named missing identity.
        self._minted_token_grpids: set[int] = set()

        # Simulate mode: the snapshot currently being executed (for handlers
        # that need GRE object data, e.g. hand materialization).
        self._current_snapshot: GameSnapshot | None = None
        # Mana payment annotations already replicated (Arena streams them
        # after the cast event; the cast handler applies them by look-ahead
        # and this set keeps the per-snapshot pass from re-applying).
        self._seen_mana_payments: set[int] = set()
        # manaIds SET into the engine pools by the current snapshot's
        # ``_sync_mana_pools`` from GRE's attested ``manaPool``. When a later
        # ManaPaid annotation consumes one of these, the source is tapped but
        # the pool is NOT re-credited (the mana was already synced) — no
        # double-credit. Reset each ``_sync_mana_pools`` call.
        self._synced_mana_ids: set[int] = set()
        # --- GRE CounterAdded/Removed reconciliation (simulate-only) ---------
        # A counter is an oracle-derived pre-comparison correction: only the
        # state the GRE annotation stream explicitly attests is ever written,
        # never fabricated. Written onto the correlated permanent as an
        # authoritative SET (double-count-proof), it makes a counter the executor
        # never fired still land while capping the engine's own trigger-driven
        # counters at the GRE total.
        #
        # Identity is anchored to the ENGINE OBJECT, not the GRE instance id.
        # GRE re-mints an object's instance id pervasively (on many events, not
        # only real zone changes, and not always via an ObjectIdChanged
        # annotation), so keying by the GRE aid makes churn look like a stint
        # boundary and drops live counters. The engine object survives all GRE
        # churn; the ledger key is its stable ``object_id``.
        #
        # A counter must still not cross a REAL zone-change boundary (blink /
        # bounce / death / reanimation). That boundary is an ENGINE event, so it
        # is detected in engine terms, from TWO complementary signals:
        #   1. battlefield membership — the object is absent from the engine
        #      battlefield zones (read directly from the zones, never via
        #      ``refs.instance_id``, which would MINT stint ids as a side
        #      effect and perturb the simulation). Covers every departure that
        #      is still visible at reconciliation time, including
        #      executor-driven resync removals that bypass ``move_to_zone``.
        #   2. the engine zone epoch — ``refs.zone_epoch(obj)`` is a pure-read
        #      monotonic count of the object's real zone changes, advanced by
        #      ``move_to_zone`` via ``note_zone_change``. A ledger records the
        #      epoch at fold time; a later epoch PROVES an intervening zone
        #      transition even when the object is back on the battlefield
        #      before the next reconciliation (an atomic blink completed
        #      within one replay step) — end-of-step membership alone cannot.
        # ``object_id`` is a construction-time constant and does NOT change on
        # a blink, so it survives GRE id churn — but it is NOT unique among
        # live objects (a copy-token impl ``copy.copy``s the copied card,
        # skipping ``__init__``, so a token copy shares its original's
        # ``object_id`` while both sit on the battlefield). The engine-object
        # key is therefore ``_counter_key(obj) = (object_id, id(obj))`` —
        # unique among live objects — and every structure keyed by it pins its
        # objects so a key is never reused while referenced. The battlefield
        # STINT is identified by (counter key, fold-time epoch).
        #
        # Ledger: engine counter key -> {engine counter name -> total}.
        self._gre_counter_ledger: dict[tuple[Any, int], dict[str, int]] = {}
        # engine counter key -> engine zone epoch observed when its ledger
        # last folded. An epoch mismatch at reconciliation retires the ledger.
        self._ledger_epoch: dict[tuple[Any, int], int] = {}
        # A counter effect is one semantic (annotation id, affected object)
        # event. Its GRE-side name is (annotation id, affected aid), but the
        # affected aid MUTATES across ObjectIdChanged hops while the annotation
        # id persists (Arena's persistent slots repeat the same annotation id,
        # possibly under a renamed aid). One semantic effect therefore has ONE
        # CANONICAL KEY — (annotation id, the aid's rename-chain ROOT) — and
        # every state surface below (pending / applied / cancelled) is keyed
        # canonically, so a repeat under ANY rename alias of the affected aid
        # resolves to the same record: it can never mint a second effect,
        # double-apply an already folded one, or bypass a cancellation.
        # Distinct affected ids of a multi-affected annotation have distinct
        # rename roots, so canonicalization never conflates them.
        #
        # aid -> the aid it was renamed FROM, for every ObjectIdChanged the
        # stream shows (accumulated game-wide; instance ids are never reused).
        # Lookups follow the chain to its root. This records GRE's identity
        # THREAD only — whether a given hop is same-stint churn or hides a zone
        # transition is judged separately, from engine evidence
        # (_advance_pending_effect); the thread itself decides key identity.
        self._counter_aid_alias: dict[int, int] = {}
        # Canonical keys folded into the ledger EXACTLY ONCE, so Arena's
        # persistent-slot repeats are idempotent AND a multi-affected-id
        # annotation whose IDs correlate at different times still applies each
        # effect once (never double-applying an already handled id).
        self._applied_counter_effects: set[tuple[int, int]] = set()
        # Effects whose aid was not yet correlated when first seen: retried every
        # snapshot until correlation becomes available (a token/new permanent may
        # first appear in the same snapshot as its CounterAdded). Never marked
        # applied until actually folded, so nothing is silently dropped. Keyed
        # canonically so a persistent-slot repeat (under the original aid or any
        # rename alias) never enqueues a duplicate; the payload additionally
        # carries
        #   current_aid — the aid as GRE names it NOW (re-keyed only across a
        #     PROVEN same-stint id churn, see _advance_pending_effect),
        #   ctx — the GRE identity context (grp/owner) captured the first time
        #     the affected object is observed, proving later folds still
        #     target the same object,
        #   seen_on_battlefield — whether the affected object has been
        #     observed on the GRE battlefield during this effect's pendency,
        #   anchor_obj / anchor_okey / anchor_pass — the engine candidate the
        #     effect was first positively correlated to (resolved AND
        #     validated), pinning the ENGINE identity the effect may fold
        #     onto, and the reconciliation pass of that capture,
        #   pending_since — the reconciliation pass on which this effect was
        #     first processed (the start of its pendency window),
        #   battlefield_since — the FIRST reconciliation pass on which GRE
        #     attested the effect's current identity ON the battlefield (None
        #     until then): the start of the relevant GRE battlefield window.
        #     For an effect first observed off the battlefield (stack
        #     resident), the window begins when the object arrives,
        #   window_epochs — the engine battlefield CENSUS at the
        #     battlefield_since pass: counter key -> zone epoch for every
        #     object then on the engine battlefield. This frozen census is
        #     the ONLY admissible continuity baseline for a fold: the
        #     resolved candidate must appear in it, with its CURRENT epoch
        #     equal to the census value — proving it sat on the engine
        #     battlefield at the window start and underwent no zone
        #     transition since, i.e. evidence brackets the COMPLETE GRE
        #     battlefield-pendency window. On the window-start pass itself
        #     the check is trivially satisfied by any validated candidate
        #     (zero-width window — same-snapshot creation/token correlation
        #     fold immediately). A candidate first observed AFTER
        #     battlefield_since is absent from the census and stays unproven
        #     FOREVER — a created, resync-injected, returned, or renamed-in
        #     object can never inherit the old effect, no matter how many
        #     passes it waits. An epoch advanced past the census value proves
        #     a real zone transition during the window (atomic blink) —
        #     cancel, however GRE renders it (same aid kept, one direct
        #     rename, or a rename chain),
        #   bf_epochs — engine counter key -> (zone epoch, reconciliation
        #     pass) at that object's EARLIEST observation on the engine
        #     battlefield during this effect's pendency (bf_pins holds the
        #     observed objects so a key is never reused while its evidence
        #     exists — census members are pinned through it, being recorded
        #     by the same sweep). Used as PRE-WINDOW churn evidence (see
        #     _churn_proven_same_stint) and kept for the unresolved surface.
        # Expiration (see _advance_pending_effect): an effect whose GRE stint
        # provably ended before correlation is CANCELLED, never applied late.
        self._pending_counter_effects: dict[tuple[int, int], dict[str, Any]] = {}
        # Monotonic count of counter-reconciliation passes (one per
        # _apply_counter_annotations call). Evidence and pendency windows are
        # stamped with it so "observed on an earlier pass" is a decidable
        # predicate — never inferred from a current-pass insertion.
        self._counter_recon_pass: int = 0
        # Canonical keys of cancelled effects — a persistent-slot repeat of a
        # cancelled annotation (under any rename alias) must not re-enqueue it.
        self._cancelled_counter_effects: set[tuple[int, int]] = set()
        # The explicit unresolved-limitation surface: one record per cancelled
        # effect (key, counter name/amount, reason). The absent counter still
        # surfaces as a normal compare divergence; this records WHY the effect
        # could not be applied, for reporting/debugging.
        self._unresolved_counter_effects: list[dict[str, Any]] = []
        # counter key -> the engine object (holds the reference so reconcile
        # can reach it to SET/cap and to clear on retirement — and so the key
        # itself stays pinned while ledgered).
        self._ledger_obj: dict[tuple[Any, int], Any] = {}
        # GRE aid -> engine token object, published by token correlation so
        # counter sync can resolve an id-less minted token that is not yet in
        # ``_engine_cards`` (that map is only rebuilt during the post-comparison
        # resync). Exposes the instance-to-object relationship, not just _grp_id.
        self._counter_token_binding: dict[int, Any] = {}
        # GRE stack iid -> engine card awaiting resolution. Kept separately
        # from _engine_cards because the instance-map rebuild (each resync)
        # clears that dict and skips stack zones.
        self._pending_stack: dict[int, Any] = {}
        # GRE stack iid -> the exact engine StackObject the executor's cast
        # pushed for that GRE cast identity. The card map above cannot answer
        # "is THIS pending spell still on the engine stack?": a source card is
        # not a unique occurrence — a triggered ability the resolution pushes
        # shares the card, and copies/recasts mint new occurrences of it. Every
        # lifecycle decision (arrival resolution, stack-exit resolution, target
        # preference binding) uses this occurrence identity; the card map is
        # kept for consumers that need the card (zone moves, _engine_cards
        # updates). Entries are popped together with _pending_stack.
        self._pending_stack_objs: dict[int, Any] = {}
        # Combat state machine (simulate mode): one declaration, one block
        # assignment, and one damage pass per GRE damage step per combat.
        self._combat_active: bool = False
        self._combat_blocks_declared: bool = False
        self._combat_damage_passes: set[str] = set()
        # game_state_id -> snapshot list index, for bounded look-ahead.
        self._gsid_index: dict[int, int] = {}
        # Simulate mode (Phase M): names of multi-ability sources whose driven
        # activation the executor could NOT disambiguate from the observed GRE
        # delta (>=2 candidate predictions matched, or none did). Their surviving
        # state mismatches carry the ``ambiguous-ability`` limitation tag — the
        # stream lacks a per-card ability-grpId map, so the exact ability driven
        # is unrecoverable. Recorded at the refusal site, consumed by the
        # validation layer's classifier.
        self._ambiguous_sources: set[str] = set()

        # Results
        self.results: list[StepResult] = []
        self._initialized: bool = False

        # Simulate-mode dirty-state tracking (recovery barrier). A transition
        # is measurable only when it starts from fully restored GRE truth.
        # Synchronization spans two INDEPENDENT domains, tracked separately so
        # restoring one can never be mistaken for restoring the other:
        #
        #   Compared-surface / P/T domain (owned by _resync_to_snapshot):
        #   _synced         — True while the executor is fully oracle-corrected
        #                     to the last snapshot it resynced to; False once a
        #                     resync could not restore a compared surface (zone
        #                     contents, life, tapped, P/T). The resync sets it
        #                     False on entry and True only on full completion,
        #                     so it owns this domain alone.
        #   _effects_broken — latched once the engine's effect layer (apply_all)
        #                     raises a non-protocol exception. Re-running it
        #                     would only re-crash, so the resync and the
        #                     turn-boundary cleanup skip it thereafter; P/T
        #                     stays uncorrected and its transitions stay
        #                     unmeasurable. This is what stops recovery from
        #                     re-triggering the same failing card-code path.
        #
        #   Operational-state domain (owned by the turn-boundary untap):
        #   _operational_dirty — set when an untap failure (protocol or not)
        #                     could not be repaired by the deterministic
        #                     fallback, leaving summoning sickness or land plays
        #                     in an unknown state. A protocol untap failure still
        #                     re-raises for classification, but only AFTER this
        #                     repair-or-latch runs, so a recorded PROTOCOL_ERROR /
        #                     QUERY_UNANSWERED can never leave the operational
        #                     domain silently dirty.
        #                     compare_state never reads those surfaces, so
        #                     a successful P/T resync would otherwise report the
        #                     executor "synced" while they stay dirty — hence a
        #                     flag the resync never touches. Once latched it
        #                     suppresses every subsequent transition (the
        #                     fail-closed floor): a suppressed step returns
        #                     before _handle_turn_info, so no later untap runs to
        #                     clear it. The deterministic fallback is what keeps
        #                     it False in the common case — latching is the rare
        #                     fallback-of-the-fallback.
        #
        # The executor is fully synchronized (_fully_synced) only when BOTH
        # domains are clean — success in one can never promote the whole.
        self._synced: bool = True
        self._effects_broken: bool = False
        self._operational_dirty: bool = False

    @property
    def _fully_synced(self) -> bool:
        """True only when every recovery domain is restored.

        Synchronization is not a single boolean: the compared-surface / P/T
        domain (``_synced``, owned by :meth:`_resync_to_snapshot`) and the
        operational-state domain (``_operational_dirty``, owned by the
        turn-boundary untap) move independently. A successful P/T resync sets
        ``_synced`` True but must never speak for the operational domain, so
        the recovery barrier gates on both: the executor may call itself fully
        synchronized only when the compared surfaces are restored AND no
        unresolved untap dirtiness remains.
        """
        return self._synced and not self._operational_dirty

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize(self, snapshot: GameSnapshot | None = None) -> None:
        """Initialize engine game state from the first full snapshot.

        Creates engine players, sets life totals, and populates opening
        hands using grpId -> card mapping.
        """
        if snapshot is None:
            # Use first snapshot from replay
            if not self.replay.snapshots:
                raise ValueError("No snapshots in replay")
            snapshot = self.replay.snapshots[0]

        # Create engine players (benchmark-parameterized: the V1 SOS engine has
        # a scripted DeterministicPlayer; the MSH engine has the intent-based one).
        for seat_id, player_info in snapshot.players.items():
            player = _make_replay_player(
                name=f"Player_{seat_id}",
                life=player_info.life_total,
            )
            self.players[seat_id] = player

        # Build hand contents from snapshot zones (GameObjects, not bare grpIds,
        # so shells can be typed from the object's own cardTypes/subtypes)
        seat_hands: dict[int, list[Any]] = {}  # seat_id -> list of GameObjects
        seat_libraries: dict[int, list[Any]] = {}  # seat_id -> list of GameObjects

        # Hidden objects (opponent hand, both libraries) appear in zone lists
        # without game_objects entries — keep a None so a shell card is
        # created and zone sizes match the GRE state.
        for zone in snapshot.zones.values():
            if zone.type == "ZoneType_Hand":
                objs = []
                for iid in zone.object_instance_ids:
                    obj = snapshot.game_objects.get(iid)
                    objs.append(obj)
                    if obj:
                        self._engine_cards[iid] = None  # placeholder
                seat_hands[zone.owner_seat_id] = objs

            elif zone.type == "ZoneType_Library":
                seat_libraries[zone.owner_seat_id] = [
                    snapshot.game_objects.get(iid)
                    for iid in zone.object_instance_ids
                ]

        # Create card instances and set up hands/libraries
        self._setup_player_zones(snapshot, seat_hands, seat_libraries)
        self._gsid_index = {
            snap.game_state_id: i for i, snap in enumerate(self.replay.snapshots)
        }
        self._initialized = True

    def _setup_player_zones(
        self,
        snapshot: GameSnapshot,
        seat_hands: dict[int, list[int]],
        seat_libraries: dict[int, list[int]],
    ) -> None:
        """Set up player zones from snapshot data."""
        from engine.card import CardImpl, Creature, Land
        from engine.game_state import GameState
        from engine.types import CardType, Zone

        for seat_id, player in self.players.items():
            # Create hand cards (None = hidden object -> shell)
            for obj in seat_hands.get(seat_id, []):
                if obj is not None:
                    card = self._create_card_from_object(obj, player)
                else:
                    card = CardImpl(name="Unknown_0", owner=player, controller=player)
                player.zones[Zone.HAND].add(card)

            # Create library cards (identities hidden -> shells; they are
            # materialized when GRE reveals them on draw)
            for obj in seat_libraries.get(seat_id, []):
                if obj is not None:
                    card = self._create_card_from_object(obj, player)
                else:
                    card = CardImpl(name="Unknown_0", owner=player, controller=player)
                player.zones[Zone.LIBRARY].add(card)

        # Build game state
        player_list = []
        for seat_id in sorted(self.players.keys()):
            player_list.append(self.players[seat_id])

        self.game = GameState(player_list)

        # Map GRE instance IDs to engine cards
        self._rebuild_instance_map(snapshot)

    def _create_card(self, grp_id: int, owner: Any) -> Any:
        """Create an engine card from a grpId, using registry if available."""
        card_name = self._grp_to_name.get(grp_id, f"Unknown_{grp_id}")

        # Try registry first
        if self.registry is not None and card_name in self.registry:
            try:
                card = self.registry.create_instance(card_name, owner=owner)
                card.controller = owner
                # Simulate-only: tag the actual grpId at creation so
                # _card_to_grp_id reads it directly instead of a name
                # reverse-lookup — which is ambiguous for multi-printing names (a
                # basic land has several printings) and returns whichever
                # printing was seen first. Gated to simulate because _create_card
                # also runs in observer mode (Seat 2 injection): observer output
                # must stay byte-identical to the pre-Phase-E baseline, whose
                # _card_to_grp_id used the name reverse-lookup here.
                if self.simulate:
                    card._grp_id = grp_id
                return card
            except Exception:
                pass

        # Fallback: create a basic card based on what we know
        return self._create_basic_card(grp_id, card_name, owner)

    _BASIC_LAND_NAMES = {"Plains", "Island", "Swamp", "Mountain", "Forest"}

    def _create_card_from_object(self, obj: Any, owner: Any) -> Any:
        """Create an engine card for a GRE GameObject, using its typed data.

        Resolves the card name via the grpId map, falling back to the
        object's own subtypes for cards outside the map — 17lands decks use
        arbitrary printings of basic lands, whose grpIds the FDN map doesn't
        carry, but the GRE object still says ``SubType_Forest``. Unresolvable
        objects become shells typed from the object's cardTypes (a Land or
        Creature shell instead of a bare CardImpl) so tapped state, P/T, and
        combat code treat them uniformly.
        """
        name = self._grp_to_name.get(obj.grp_id, "")
        if not name and "CardType_Land" in obj.card_types:
            for subtype in obj.subtypes:
                basic = subtype.removeprefix("SubType_")
                if basic in self._BASIC_LAND_NAMES:
                    name = basic
                    break

        if name and self.registry is not None and name in self.registry:
            try:
                card = self.registry.create_instance(name, owner=owner)
                card.controller = owner
                card._grp_id = obj.grp_id
                return card
            except Exception:
                pass

        from engine.card import CardImpl, Creature, Land

        display_name = name or f"Unknown_{obj.grp_id}"
        if "CardType_Creature" in obj.card_types:
            card = Creature(
                name=display_name,
                owner=owner,
                controller=owner,
                base_power=obj.power or 0,
                base_toughness=obj.toughness or 0,
            )
        elif "CardType_Land" in obj.card_types:
            card = Land(name=display_name, owner=owner, controller=owner)
        else:
            card = CardImpl(name=display_name, owner=owner, controller=owner)
        card._grp_id = obj.grp_id
        return card

    def _create_basic_card(self, grp_id: int, card_name: str, owner: Any) -> Any:
        """Create a basic engine card without registry."""
        from engine.card import Creature, Land, CardImpl
        from engine.types import CardType, ManaCost

        # Use name to guess card type
        basic_lands = {"Plains", "Island", "Swamp", "Mountain", "Forest"}

        if card_name in basic_lands:
            card = Land(name=card_name, owner=owner, controller=owner)
            # Simulate-only: carry the actual GRE grpId, not the name — a basic
            # land name maps to several printings, so the name reverse-lookup in
            # _card_to_grp_id would otherwise pick the wrong (first) printing.
            # Gated to simulate because _create_basic_card also runs in observer
            # mode (Seat 2 land plays of unregistered basic lands); observer
            # output must stay byte-identical to the pre-Phase-E baseline, which
            # did not tag the grpId here.
            if self.simulate:
                card._grp_id = grp_id
            return card

        # For unknown cards, create a generic CardImpl
        card = CardImpl(name=card_name, owner=owner, controller=owner)
        card._grp_id = grp_id  # Store for tracking
        return card

    def _snapshot_zone_groups(
        self, snapshot: GameSnapshot
    ) -> list[tuple[Any, int, str, list[Any], int]]:
        """Group a snapshot's zone objects per (engine zone, seat).

        Returns ``(engine_zone, seat_id, gre_zone_type, objects,
        expected_count)`` tuples. Per-seat GRE zones (hand, library,
        graveyard) yield one group each. Shared GRE zones (battlefield,
        exile, stack — ``ownerSeatId == 0``) are split into one group per
        known player, routing each object by its controller (battlefield) or
        owner seat, so they line up with the engine's per-player zone model.
        Empty groups are included so callers can detect engine-side excess
        cards.

        ``expected_count`` is how many objects GRE says the group holds —
        for per-seat zones the zone's id-list length (hidden objects, e.g.
        opponent hand cards, appear as ids WITHOUT game_objects entries, so
        ``len(objects)`` undercounts them); for shared zones, whose objects
        are all visible, it equals ``len(objects)``.
        """
        from engine.types import Zone

        groups: list[tuple[Any, int, str, list[Any], int]] = []
        for snap_zone in snapshot.zones.values():
            engine_zone_name = _GRE_ZONE_TO_ENGINE.get(snap_zone.type)
            if engine_zone_name is None:
                continue
            try:
                engine_zone = Zone(engine_zone_name)
            except ValueError:
                continue

            objs = [
                obj
                for iid in snap_zone.object_instance_ids
                if (obj := snapshot.game_objects.get(iid)) is not None
            ]
            if snap_zone.owner_seat_id:
                groups.append((
                    engine_zone, snap_zone.owner_seat_id, snap_zone.type,
                    objs, len(snap_zone.object_instance_ids),
                ))
                continue

            by_seat: dict[int, list[Any]] = {seat: [] for seat in self.players}
            route_by_controller = snap_zone.type in _SHARED_ZONE_ROUTE_BY_CONTROLLER
            for obj in objs:
                if route_by_controller:
                    seat = obj.controller_seat_id or obj.owner_seat_id
                else:
                    seat = obj.owner_seat_id or obj.controller_seat_id
                if seat in by_seat:
                    by_seat[seat].append(obj)
            for seat, group in sorted(by_seat.items()):
                groups.append((engine_zone, seat, snap_zone.type, group, len(group)))
        return groups

    def _rebuild_instance_map(self, snapshot: GameSnapshot) -> None:
        """Rebuild the GRE instanceId -> engine card mapping.

        Prior bindings are kept when they still hold (the same engine card
        object is still in the zone GRE puts the instance id in) — only the
        unmatched remainder is order-matched by grpId. Without this, two
        same-name permanents (basic lands especially) swap identities on
        every rebuild, flapping per-object state like tapped comparisons.
        """
        old = dict(self._engine_cards)
        self._engine_cards.clear()

        for engine_zone_enum, seat_id, zone_type_str, objs, expected_count in self._snapshot_zone_groups(snapshot):
            if zone_type_str in ("ZoneType_Library", "ZoneType_Stack"):
                continue  # hidden identities / game-level stack — nothing to correlate
            player = self.players.get(seat_id)
            if player is None:
                continue

            available = player.zones[engine_zone_enum].get_all()

            # Pass 1: keep still-valid prior bindings (identity match).
            pending: list[Any] = []
            for obj in objs:
                bound = old.get(obj.instance_id)
                if bound is not None and any(c is bound for c in available):
                    self._engine_cards[obj.instance_id] = bound
                    available = [c for c in available if c is not bound]
                else:
                    pending.append(obj)

            # Pass 2: order-match the remainder by grpId (card name).
            grp_id_cards: dict[int, list[Any]] = {}
            for card in available:
                grp_id_cards.setdefault(self._card_to_grp_id(card), []).append(card)

            for obj in pending:
                candidates = grp_id_cards.get(obj.grp_id, [])
                if candidates:
                    self._engine_cards[obj.instance_id] = candidates.pop(0)

    def execute_step(
        self,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
    ) -> StepResult:
        """Process one snapshot transition and validate state.

        For Seat 1 actions, infers the action from the diff and executes
        it through the engine API. For Seat 2 actions, observes what was
        played from public zones and injects state changes directly.
        """
        if not self._initialized:
            raise RuntimeError("Must call initialize() before execute_step()")

        result = StepResult(snapshot_id=curr_snapshot.game_state_id)

        # Recovery barrier (simulate mode): a transition is measurable only
        # from fully restored GRE truth — across BOTH synchronization domains
        # (compared/P/T surfaces AND operational untap state). If a PRIOR step
        # left either domain dirty, recover before touching anything else. This
        # is checked here — before _handle_turn_info, whose turn-boundary
        # cleanup/untap can itself dirty the executor — so an in-step failure is
        # measured (it started clean) while a carried-over dirty state is not.
        #   - Compared surfaces recover by resyncing to the previous snapshot.
        #   - Operational dirtiness (an unrecoverable untap) has no mid-turn
        #     reconstruction point, so it forces suppression outright — and,
        #     since suppression returns before _handle_turn_info, the latch
        #     then persists (the fail-closed floor for a broken untap).
        # If recovery can't complete, the transition is unmeasurable: record
        # REPLAY_INFRA, emit no comparison from dirty state, and resync forward
        # so a later step can still recover.
        if self.simulate and not self._fully_synced:
            recovered = (
                not self._operational_dirty
                and self._resync_to_snapshot(prev_snapshot, result)
            )
            if not recovered:
                return self._suppress_unmeasurable(
                    prev_snapshot, curr_snapshot, result
                )

        # Detect phase/step changes
        self._handle_turn_info(
            prev_snapshot.turn_info, curr_snapshot.turn_info, result
        )

        # Get actions from the snapshot
        actions = curr_snapshot.actions
        if not actions:
            # Try to infer actions from diff
            from silverquillm.replay.state import infer_actions
            actions = infer_actions(prev_snapshot, curr_snapshot, self.card_id_map)

        if self.simulate:
            return self._execute_step_simulate(actions, prev_snapshot, curr_snapshot, result)

        if not actions:
            # Phase transition only — still compare state for phase-induced changes
            result.action_type = "phase_transition"
            result.skipped = True
            result.skip_reason = "no actions detected"
            self._sync_zones(curr_snapshot)
            self._reconcile_life_totals(prev_snapshot, curr_snapshot)
            mismatches = self.compare_state(curr_snapshot)
            result.mismatches.extend(mismatches)
            result.success = len(result.mismatches) == 0
            return result

        # Process each action
        for action in actions:
            if action.action_type in ("combat", "phase_transition"):
                continue  # Phase transitions tracked; damage handled by life reconciliation


            result.action_type = action.action_type
            result.seat_id = action.player_seat_id
            result.card_name = action.card_name

            if action.player_seat_id == self.replay.seat_id:
                # Seat 1: full validation
                self._execute_seat1_action(action, prev_snapshot, curr_snapshot, result)
            else:
                # Seat 2: oracle injection
                self._inject_seat2_action(action, prev_snapshot, curr_snapshot, result)

        # Sync engine zones for untracked card appearances, then compare
        self._sync_zones(curr_snapshot)
        self._reconcile_life_totals(prev_snapshot, curr_snapshot)
        mismatches = self.compare_state(curr_snapshot)
        result.mismatches.extend(mismatches)
        result.success = len(result.mismatches) == 0

        return result

    # ------------------------------------------------------------------
    # Simulate mode: compare first, then oracle-resync
    # ------------------------------------------------------------------

    def _execute_step_simulate(
        self,
        actions: list[ReplayAction],
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> StepResult:
        """Simulate-mode step: drive the engine, compare, THEN resync.

        The comparison runs against whatever state the engine actually
        reached, so divergences are real signal. Afterwards the engine is
        oracle-corrected to the GRE snapshot so every step validates
        independently instead of cascading one divergence forever.
        """
        self._current_snapshot = curr_snapshot

        # At a GRE phase/step transition, SET the engine pools to the mana GRE
        # attests was still floating at the end of the previous step (its
        # manaPool), replacing the old *unconditional* pool-empty at that
        # boundary. Floating mana carries exactly as far as GRE holds it (empty
        # when GRE attests empty — the mundane step-end case, byte-identical to
        # the old empty). WITHIN a step the pool is left to accumulate as
        # before: casts/activations pay engine-known costs and the ManaPaid
        # look-ahead pre-credits their payments across snapshots, so emptying
        # mid-step would strand a payment already credited for a later cast.
        prev_ti, curr_ti = prev_snapshot.turn_info, curr_snapshot.turn_info
        if (curr_ti.phase, curr_ti.step) != (prev_ti.phase, prev_ti.step):
            self._sync_mana_pools(prev_snapshot)

        # Mana payments (ManaPaid annotations) tap the paying lands and fill
        # the payer's pool before any cast in this step tries to pay.
        self._apply_mana_payments(curr_snapshot, result)

        # Combat: declare attackers/blocks and deal damage through the engine
        # as the GRE stream reveals them.
        self._simulate_combat_transitions(curr_snapshot, result)

        # Draws: any hand arrival without zone-move provenance is a draw (or
        # hidden-zone tutor) — pull it through the engine's library.
        self._simulate_hand_draws(prev_snapshot, curr_snapshot, result)

        # Hidden-origin plays (opponent casts, opponent land plays) have no
        # pre-move object for infer_actions to see — synthesize them from the
        # arrival side, where the card is public.
        result.synthesized_actions = self._infer_hidden_origin_actions(
            actions, prev_snapshot, curr_snapshot
        )
        actions = actions + result.synthesized_actions

        for action in actions:
            action_type = action.action_type
            if action_type in ("combat", "phase_transition", "draw"):
                # combat: driven from GRE attack/block state (task: combat steps)
                # draw: handled by _simulate_hand_draws above
                continue

            result.action_type = action_type
            result.seat_id = action.player_seat_id
            result.card_name = action.card_name

            # Both seats run through the engine: every input the engine needs
            # is public at action time (casts reveal the card; ManaPaid names
            # the lands; SubmittedTargets names the targets).
            if action_type == "land_play":
                self._execute_land_play(action, result)
            elif action_type == "spell_cast":
                self._simulate_spell_cast(action, prev_snapshot, curr_snapshot, result)
            elif action_type == "creature_death":
                self._execute_creature_death(action, result)
            elif action_type == "zone_transition":
                self._simulate_zone_transition(action, prev_snapshot, curr_snapshot, result)
            elif action_type in ("ability_activation", "ability_resolution"):
                self._simulate_ability_resolution(action, prev_snapshot, curr_snapshot, result)

        if not actions:
            result.action_type = "phase_transition"

        # Arrival-aligned resolution: GRE routinely resolves a permanent spell
        # SILENTLY — the card moves stack->battlefield with no ObjectIdChanged
        # and no action, so infer_actions sees nothing and the engine spell
        # would sit on the stack until this step's post-comparison resync flush,
        # one snapshot too late. When the current snapshot already attests a
        # cast spell's permanent on the battlefield, that IS its resolution
        # evidence: resolve that specific pending object now, before comparison.
        self._resolve_arrived_spells(curr_snapshot, result)

        # Correlate engine-minted tokens to their GRE grpId before comparing, so
        # a token the engine correctly minted reads as its real identity instead
        # of an anonymous id-0 shell that mis-compares against the GRE token.
        self._correlate_tokens(curr_snapshot)

        # Sync counter state from the GRE CounterAdded/Removed stream onto the
        # correlated permanents (+1/+1 counters the executor never fired, plus
        # named counters like Drake Hatcher's incubation) before comparison — an
        # authoritative SET, so no double-count with engine-driven counters.
        self._apply_counter_annotations(curr_snapshot)

        # Honest comparison against the state the engine actually reached.
        result.mismatches.extend(self.compare_state(curr_snapshot))

        # Oracle-resync to GRE truth so the next step starts clean. The resync
        # is internally guarded and records (via _synced) whether it fully
        # restored the compared surfaces — register_triggers on injected
        # permanents and apply_all under the P/T re-derivation both run card
        # code. A crash there does not discard the comparisons this step already
        # recorded; it marks the executor dirty, and the recovery barrier at the
        # top of the next step restores GRE truth or suppresses that step as
        # unmeasurable. Protocol exceptions still propagate for classification.
        #
        # Crucially, the resync owns ONLY the compared/P/T domain: it sets
        # _synced but never _operational_dirty. So an untap failure earlier in
        # this step (from _handle_turn_info) that latched operational dirtiness
        # survives this resync even when P/T restores cleanly — the two domains
        # are independent, and _fully_synced gates on both.
        self._resync_to_snapshot(curr_snapshot, result)

        result.success = not (
            result.mismatches or result.engine_failures or result.infra_failures
        )
        return result

    def _suppress_unmeasurable(
        self,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> StepResult:
        """Handle a transition that can't be measured from restored GRE truth.

        Reached from the recovery barrier when a dirty domain could not be
        restored: either a recovery resync to the previous snapshot did not
        complete (compared/P/T domain), or operational untap state is latched
        dirty with no mid-turn reconstruction point (operational domain). The
        engine state is dirty, so emitting a state comparison would report
        residue from the earlier failure, not this transition — record a
        REPLAY_INFRA failure instead and emit no mismatches. A forward resync to
        the current snapshot is still attempted so a later step has a fresh
        chance to recover the compared surfaces (self-heal); if the effect layer
        is broken it is skipped rather than re-triggered. Operational dirtiness
        is never cleared here — and because this path returns before
        _handle_turn_info, no later untap runs to clear it either, so a latched
        operational domain stays suppressed (the fail-closed floor).
        """
        result.action_type = "unmeasurable"
        result.skipped = True
        result.skip_reason = "recovery incomplete (dirty state)"
        result.infra_failures.append(
            "unmeasurable transition: executor not resynced to GRE snapshot "
            f"{prev_snapshot.game_state_id} (recovery incomplete); comparison "
            "suppressed"
        )
        self._resync_to_snapshot(curr_snapshot, result)
        result.success = False
        return result

    _COMBAT_DAMAGE_STEPS = {"Step_FirstStrikeDamage", "Step_CombatDamage"}
    _COMBAT_GRE_STEPS = {
        "Step_BeginCombat", "Step_DeclareAttack", "Step_DeclareBlock",
        "Step_FirstStrikeDamage", "Step_CombatDamage", "Step_EndCombat",
    }

    def _simulate_combat_transitions(self, curr_snapshot: GameSnapshot, result: StepResult) -> None:
        """Drive engine combat from the GRE combat state on game objects.

        Attackers are declared when ``attackState`` appears (engine taps
        non-vigilance attackers), blocks when ``blockInfo`` names the blocked
        attackers, and the engine's combat_damage_step computes damage,
        lifelink, trample, deathtouch, and the resulting deaths at the first
        damage step. One declaration/damage pass per GRE combat.
        """
        if self.game is None:
            return
        step = curr_snapshot.turn_info.step
        in_combat = (
            curr_snapshot.turn_info.phase == "Phase_Combat"
            or step in self._COMBAT_GRE_STEPS
        )

        if self._combat_active and (step == "Step_EndCombat" or not in_combat):
            from engine.combat import end_combat_step
            try:
                end_combat_step(self.game)
            except Exception as exc:
                result.engine_failures.append(
                    f"end_combat_step: {type(exc).__name__}: {exc}"
                )
            self._combat_active = False
            self._combat_blocks_declared = False
            self._combat_damage_passes.clear()

        if not in_combat:
            return

        bf_objects = curr_snapshot.get_zone_objects("ZoneType_Battlefield")

        if not self._combat_active:
            # AttackState_Declared precedes the tap by one snapshot; the
            # engine declaration (which taps) matches AttackState_Attacking.
            attackers = [
                card
                for obj in bf_objects
                if obj.attack_state == "AttackState_Attacking"
                and (card := self._engine_cards.get(obj.instance_id)) is not None
            ]
            if attackers:
                from engine.combat import declare_attackers_step
                try:
                    declare_attackers_step(self.game, attackers)
                    self._combat_active = True
                except Exception as exc:
                    result.engine_failures.append(
                        f"declare_attackers_step: {type(exc).__name__}: {exc}"
                    )

        if self._combat_active and not self._combat_blocks_declared:
            assignments: dict[Any, list[Any]] = {}
            for obj in bf_objects:
                if not obj.blocking_attacker_ids:
                    continue
                blocker = self._engine_cards.get(obj.instance_id)
                if blocker is None:
                    continue
                attackers_blocked = [
                    card
                    for aid in obj.blocking_attacker_ids
                    if (card := self._engine_cards.get(aid)) is not None
                ]
                if attackers_blocked:
                    assignments[blocker] = attackers_blocked
            if assignments or step in self._COMBAT_DAMAGE_STEPS:
                if assignments:
                    from engine.combat import declare_blockers_step
                    try:
                        declare_blockers_step(self.game, assignments)
                    except Exception as exc:
                        result.engine_failures.append(
                            f"declare_blockers_step: {type(exc).__name__}: {exc}"
                        )
                self._combat_blocks_declared = True

        if self._combat_active and step in self._COMBAT_DAMAGE_STEPS:
            # Mirror the GRE damage-step sequence: the first-strike pass at
            # Step_FirstStrikeDamage, the normal pass at Step_CombatDamage —
            # so each snapshot compares against only the damage GRE has
            # actually dealt. Each pass runs once per combat.
            sub_step = (
                "first_strike" if step == "Step_FirstStrikeDamage" else "normal"
            )
            if sub_step not in self._combat_damage_passes:
                self._combat_damage_passes.add(sub_step)
                from engine.combat import combat_damage_step
                # Multi-blocker damage order: the engine raises an ordering
                # Player Query; answer it with the replay's observed outcome
                # (blockers that die first were assigned damage first).
                ordering_intents = self._mint_damage_order_intents(curr_snapshot)
                try:
                    combat_damage_step(self.game, sub_step=sub_step)
                except Exception as exc:
                    result.engine_failures.append(
                        f"combat_damage_step: {type(exc).__name__}: {exc}"
                    )
                finally:
                    for player, intent_name in ordering_intents:
                        player.end_intent(intent_name)

    def _mint_damage_order_intents(
        self, curr_snapshot: GameSnapshot
    ) -> list[tuple[Any, str]]:
        """Answer damage-order queries from the replay's observed outcome.

        For each attacker blocked by 2+ creatures, look ahead for which
        blockers leave the battlefield — those were assigned (lethal)
        damage first, in death order. Mints one ordering Intent per such
        attacker on its controller; the caller ends them after the damage
        pass. Attackers that share a printed name are skipped (their
        pattern-routed intents would be ambiguous); the baseline's
        first-offered order applies there, and compare-first records any
        resulting divergence.
        """
        from engine.decisions import Decision, GameRef
        from engine.intent_player import Intent

        by_attacker: dict[int, list[int]] = {}
        for obj in curr_snapshot.get_zone_objects("ZoneType_Battlefield"):
            for aid in obj.blocking_attacker_ids:
                by_attacker.setdefault(aid, []).append(obj.instance_id)

        multi = {a: b for a, b in by_attacker.items() if len(b) >= 2}
        if not multi:
            return []
        names = [
            getattr(self._engine_cards.get(a), "name", None) for a in multi
        ]
        intents: list[tuple[Any, str]] = []
        for aid, blocker_iids in multi.items():
            attacker = self._engine_cards.get(aid)
            if attacker is None:
                continue
            if names.count(getattr(attacker, "name", None)) > 1:
                continue  # same-name attackers — pattern would be ambiguous
            controller = getattr(attacker, "controller", None)
            if controller is None or not hasattr(controller, "start_intent"):
                continue
            preferences: list[Any] = []
            for iid in self._blocker_death_order(blocker_iids, curr_snapshot):
                card = self._engine_cards.get(iid)
                if card is None:
                    continue
                engine_iid = self._engine_instance_id(card)
                if engine_iid is not None:
                    preferences.append(Decision.obj(instance=engine_iid))
                elif getattr(card, "name", ""):
                    preferences.append(Decision.obj(name=card.name))
            if not preferences:
                continue
            intent_name = f"replay_order_{aid}"
            controller.start_intent(intent_name, Intent(
                pattern=GameRef(card=frozenset({("name", attacker.name)})),
                preferences=tuple(preferences),
            ))
            intents.append((controller, intent_name))
        return intents

    def _blocker_death_order(
        self, blocker_iids: list[int], curr_snapshot: GameSnapshot
    ) -> list[int]:
        """Blockers ordered by observed death (first to leave first), survivors last.

        Heuristic: "left the battlefield within the window" conflates combat
        death with bounce/exile or a follow-up removal spell — acceptable
        because the result only seeds an ordering *preference*; a wrong
        order surfaces as an honest compare-first mismatch, not silent
        corruption.
        """
        start = self._gsid_index.get(curr_snapshot.game_state_id, 0)
        deaths: dict[int, int] = {}
        alive = set(blocker_iids)
        for k, snap in enumerate(self.replay.snapshots[start : start + _DEATH_LOOKAHEAD]):
            if not alive:
                break
            bf_ids = {
                iid
                for zone in snap.zones.values()
                if zone.type == "ZoneType_Battlefield"
                for iid in zone.object_instance_ids
            }
            for iid in list(alive):
                if iid not in bf_ids:
                    deaths[iid] = k
                    alive.discard(iid)
        ordered = sorted(deaths, key=lambda i: deaths[i])
        ordered.extend(i for i in blocker_iids if i not in deaths)
        return ordered

    def _simulate_hand_draws(
        self,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Draw through the engine for every library-origin hand arrival.

        A new hand instance id is a draw when its ObjectIdChanged origin sat
        in the library — the normal case: GRE re-mints the hidden library
        card's id as it reaches the hand — or when it has no provenance at
        all (hidden-zone tutors). Arrivals whose origin was a *visible* zone
        (battlefield bounce, graveyard recursion) are zone moves, driven by
        the zone_transition handler instead. The engine draws a shell from
        its library; when GRE reveals the drawn card's identity (own seat),
        the shell is materialized into the real card so later casts exercise
        the actual implementation.
        """
        from engine.card import CardImpl
        from engine.game import draw_card
        from engine.types import Zone
        from silverquillm.replay.state import extract_object_id_changes

        origin_of = {
            new: orig
            for orig, new in extract_object_id_changes(curr_snapshot.annotations).items()
        }
        prev_zone_of: dict[int, str] = {}
        for zone in prev_snapshot.zones.values():
            for iid in zone.object_instance_ids:
                prev_zone_of[iid] = zone.type

        def _is_draw(iid: int) -> bool:
            orig = origin_of.get(iid)
            if orig is None:
                return True  # no provenance — hidden-zone arrival
            src = prev_zone_of.get(orig)
            return src is None or src == "ZoneType_Library"

        prev_hand_iids: dict[int, set[int]] = {}
        for zone in prev_snapshot.zones.values():
            if zone.type == "ZoneType_Hand":
                prev_hand_iids[zone.owner_seat_id] = set(zone.object_instance_ids)

        for zone in curr_snapshot.zones.values():
            if zone.type != "ZoneType_Hand":
                continue
            seat = zone.owner_seat_id
            player = self.players.get(seat)
            if player is None:
                continue
            prev_ids = prev_hand_iids.get(seat, set())
            if (
                curr_snapshot.turn_info.turn_number == 0
                and prev_ids
                and not (prev_ids & set(zone.object_instance_ids))
            ):
                # Mulligan re-deal: the whole hand went back before the new
                # one was dealt — return the engine hand to the library so
                # the deal below draws a fresh hand instead of a second one.
                hand = player.zones[Zone.HAND]
                library = player.zones[Zone.LIBRARY]
                for card in hand.get_all():
                    hand.remove(card)
                    library.add(card)
            new_iids = [
                iid
                for iid in zone.object_instance_ids
                if iid not in prev_ids and _is_draw(iid)
            ]
            for iid in new_iids:
                try:
                    drawn = draw_card(self.game, player)
                except Exception as exc:
                    # Draw triggers run card code — a crash there is a
                    # per-draw failure, not a step abort.
                    if _is_protocol_exception(exc):
                        raise
                    result.engine_failures.append(
                        f"draw_card (seat {seat}): {type(exc).__name__}: {exc}"
                    )
                    continue
                obj = curr_snapshot.game_objects.get(iid)
                if drawn is None:
                    # The engine library ran dry before GRE's did. This is an
                    # executor-side artifact: a library-manipulating effect
                    # resolving against the engine's own library — most often
                    # Consuming Aberration's per-cast mill, now that the
                    # spell-cast event fires — depletes it at a depth that
                    # cannot mirror GRE's hidden library order. GRE attests the
                    # draw happened, so reconstruct the drawn card into hand (a
                    # zone reconciliation, like _sync_zones — no draw trigger is
                    # fired, since draw_card performed no engine draw): the
                    # revealed identity when GRE gives one, else the same
                    # ``Unknown_0`` shell the initial deal uses for a hidden
                    # card. Either way the hand count stays correct and the only
                    # residue is an honest engine-library-count divergence,
                    # never a crash that suppresses the rest of the game.
                    hand = player.zones[Zone.HAND]
                    if obj is not None and obj.grp_id:
                        real = self._create_card_from_object(obj, player)
                    else:
                        real = CardImpl(
                            name="Unknown_0", owner=player, controller=player
                        )
                    hand.add(real)
                    self._engine_cards[iid] = real
                    continue
                if obj is not None and obj.grp_id:
                    # Materialize the revealed identity in place of the shell.
                    hand = player.zones[Zone.HAND]
                    hand.remove(drawn)
                    real = self._create_card_from_object(obj, player)
                    hand.add(real)
                    self._engine_cards[iid] = real
                else:
                    self._engine_cards[iid] = drawn

    def _infer_hidden_origin_actions(
        self,
        actions: list[ReplayAction],
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
    ) -> list[ReplayAction]:
        """Synthesize actions for plays whose origin object was hidden.

        ``infer_actions`` only reports moves whose pre-move object exists in
        the previous snapshot — a card cast or played from a hidden hand has
        no such object, so the opponent's entire game is invisible to it.
        The card itself is public the moment it arrives, so this fills the
        gap from the arrival side: a new card on the stack is a spell_cast
        and a new land on the battlefield is a land_play, unless an existing
        action or a visible-zone provenance already accounts for it.
        """
        from silverquillm.replay.state import extract_object_id_changes

        covered = {a.instance_id for a in actions if a.instance_id}
        origin_of = {
            new: orig
            for orig, new in extract_object_id_changes(curr_snapshot.annotations).items()
        }
        prev_zone_of: dict[int, str] = {}
        prev_ids_by_type: dict[str, set[int]] = {}
        for zone in prev_snapshot.zones.values():
            ids = prev_ids_by_type.setdefault(zone.type, set())
            for iid in zone.object_instance_ids:
                ids.add(iid)
                prev_zone_of[iid] = zone.type

        synthesized: list[ReplayAction] = []
        turn = curr_snapshot.turn_info.turn_number
        active = curr_snapshot.turn_info.active_player

        for zone in curr_snapshot.zones.values():
            if zone.type not in ("ZoneType_Stack", "ZoneType_Battlefield"):
                continue
            for iid in zone.object_instance_ids:
                if iid in prev_ids_by_type.get(zone.type, set()) or iid in covered:
                    continue
                obj = curr_snapshot.game_objects.get(iid)
                if obj is None or obj.type != "GameObjectType_Card":
                    continue
                # A visible-zone origin means infer_actions saw the move (or
                # will be reconciled by resync) — only hidden origins here.
                src_zone = prev_zone_of.get(origin_of.get(iid, -1))
                if src_zone is not None and src_zone != "ZoneType_Hand":
                    continue
                seat = obj.controller_seat_id or obj.owner_seat_id
                card_name = self._grp_to_name.get(obj.grp_id, f"Unknown_{obj.grp_id}")
                if zone.type == "ZoneType_Stack":
                    action_type = "spell_cast"
                elif "CardType_Land" in obj.card_types:
                    action_type = "land_play"
                else:
                    continue  # tokens/direct entries — resync reconciles
                synthesized.append(ReplayAction(
                    action_type=action_type,
                    turn_number=turn,
                    active_player=active,
                    player_seat_id=seat,
                    card_name=card_name,
                    grp_id=obj.grp_id,
                    instance_id=iid,
                    source_zone="ZoneType_Hand",
                    dest_zone=zone.type,
                ))
        return synthesized

    # Arena mana color enum in ManaPaid annotations (WUBRG order) →
    # engine ManaType values (single-letter tokens).
    _GRE_MANA_COLOR: dict[int, str] = {
        1: "W", 2: "U", 3: "B", 4: "R", 5: "G", 6: "C",
    }

    # GRE manaPool color strings → engine ManaType tokens.
    _GRE_MANA_POOL_COLOR: ClassVar[dict[str, str]] = {
        "ManaColor_White": "W",
        "ManaColor_Blue": "U",
        "ManaColor_Black": "B",
        "ManaColor_Red": "R",
        "ManaColor_Green": "G",
        "ManaColor_Colorless": "C",
    }

    def _sync_mana_pools(self, snapshot: GameSnapshot) -> None:
        """SET each engine ManaPool to GRE's attested floating mana (simulate).

        Replaces the unconditional pool-empty at GRE phase/step transitions
        with sync-to-attested: the engine pool is set to exactly the
        ``manaPool`` GRE attests on *snapshot* — floating mana carried across
        as GRE holds it, empty when GRE attests empty. The carry window is
        therefore whatever GRE attests; there is no guessed carry rule (this
        is categorically not per-turn floating-mana reconstruction — every
        credited mana is a specific attested ``(manaId, color, source)``
        object in the player message, exactly like the life-total sync).

        SET, never additive: the pool is emptied first, so this never creates
        mana the snapshot does not attest. The source lands are tapped (GRE
        shows them tapped the moment they float mana), and each synced manaId
        is recorded so the ManaPaid pass that later consumes it taps the
        source but does NOT re-credit the pool (:meth:`_apply_one_mana_payment`).

        Called with the PREVIOUS snapshot: its attested pool is the floating
        mana available going into the current snapshot's casts/activations
        (mana consumed within a snapshot is already gone from that snapshot's
        own attestation). A no-op for engine-known debits, which the next
        snapshot's SET re-trues from GRE.
        """
        from engine.types import ManaType

        self._synced_mana_ids = set()
        for seat, pinfo in snapshot.players.items():
            player = self.players.get(seat)
            if player is None:
                continue
            pool = getattr(player, "mana_pool", None)
            if pool is None:
                continue
            pool.empty()
            for entry in pinfo.mana_pool:
                token = self._GRE_MANA_POOL_COLOR.get(entry.color)
                if token is None:
                    # Unknown color: cannot represent it without fabricating —
                    # leave it out (the activation stays honestly unfunded).
                    continue
                pool.add(ManaType(token), max(entry.count, 0))
                self._synced_mana_ids.add(entry.mana_id)
                src = self._engine_cards.get(entry.src_instance_id)
                if src is not None:
                    src.is_tapped = True

    def _apply_mana_payments(self, snapshot: GameSnapshot, result: StepResult) -> None:
        """Replicate ManaPaid annotations: tap the source, credit the pool.

        ``affectorId`` is the paying permanent's GRE instance id; ``color``
        is the Arena color enum. The payer's pool is credited so the
        subsequent cast_spell in this step can pay its cost. Mana that was
        already floating (SET into the pool by :meth:`_sync_mana_pools` from
        GRE's attested ``manaPool``) is not re-credited here — its manaId is
        retired instead — so a float-then-spend never double-credits.
        """
        for ann in snapshot.annotations:
            if "AnnotationType_ManaPaid" not in ann.type:
                continue
            self._apply_one_mana_payment(ann)

    @staticmethod
    def _ann_mana_id(ann: Any) -> int | None:
        """The consumed manaId a ManaPaid annotation carries in ``details.id``."""
        mana_id = ann.details.get("id")
        if isinstance(mana_id, list):
            mana_id = mana_id[0] if mana_id else None
        return mana_id

    def _apply_one_mana_payment(self, ann: Any, tap: bool = True) -> None:
        """Credit the payer's pool (once per annotation) and tap the source.

        The pool credit is deduped by annotation id — a cast's look-ahead
        may have credited it already. The tap is NOT applied by look-ahead
        (``tap=False``): GRE shows the land tapped only in the annotation's
        home snapshot, so tapping early would mis-compare that snapshot and
        the dedup would then leave the land untapped when GRE taps it. The
        per-snapshot pass taps at exactly the GRE-observed moment.

        When the consumed mana was already SET into the pool by
        :meth:`_sync_mana_pools` (its manaId is in ``_synced_mana_ids``), the
        source is still tapped but the pool is NOT credited — the mana is
        already there — and the manaId is retired so it cannot be skipped
        twice. This is the no-double-credit rule for float-then-spend.
        """
        from engine.types import ManaType

        source = self._engine_cards.get(ann.affector_id)
        if source is None:
            return
        if tap:
            source.is_tapped = True
        if ann.id in self._seen_mana_payments:
            return
        self._seen_mana_payments.add(ann.id)
        mana_id = self._ann_mana_id(ann)
        if mana_id is not None and mana_id in self._synced_mana_ids:
            # Already floating in the pool via _sync_mana_pools — tap only.
            self._synced_mana_ids.discard(mana_id)
            return
        controller = getattr(source, "controller", None)
        pool = getattr(controller, "mana_pool", None)
        if pool is None:
            return
        color_code = ann.details.get("color")
        if isinstance(color_code, list):
            color_code = color_code[0] if color_code else None
        token = self._GRE_MANA_COLOR.get(color_code, "C")
        pool.add(ManaType(token), 1)

    def _apply_spell_mana_lookahead(self, spell_iid: int, curr_snapshot: GameSnapshot) -> None:
        """Apply the ManaPaid annotations that fund *spell_iid*, by look-ahead.

        Arena streams payment annotations in the snapshots AFTER the cast
        event, each tagged with the funded spell's stack instance id in
        ``affectedIds``. The cast needs them in the pool now; the seen-set
        keeps the regular per-snapshot pass from applying them twice.
        """
        if not spell_iid:
            return
        # The window is NOT cut short when the spell leaves the stack:
        # Arena streams payment annotations even after the paid-for object
        # is deleted (fast auto-resolves), and instance ids are never
        # reused within a game, so the affected-ids filter alone is exact.
        start = self._gsid_index.get(curr_snapshot.game_state_id, 0)
        for snap in self.replay.snapshots[start : start + _ANNOTATION_LOOKAHEAD]:
            for ann in snap.annotations:
                if (
                    "AnnotationType_ManaPaid" in ann.type
                    and spell_iid in ann.affected_ids
                ):
                    # Credit only — the tap lands at the annotation's home
                    # snapshot, when GRE also shows the source tapped.
                    self._apply_one_mana_payment(ann, tap=False)

    def _apply_cast_time_evidence(
        self, card: Any, spell_iid: int, curr_snapshot: GameSnapshot
    ) -> None:
        """Stamp observed cast-time choices onto *card* before it is cast.

        Feeds the enters-with-counters primitive (rule 614.1c) the evidence its
        ``enters_battlefield_with`` hook reads:

        * **X** — the value chosen for ``{X}`` in the cast, derived from the
          count of ManaPaid annotations funding this cast minus the printed
          non-X mana cost, divided by the number of ``{X}`` symbols. Scoped to
          entry-counter consumers (a permanent whose impl defines
          ``enters_battlefield_with`` and whose cost has ``{X}``) so that X
          burn/drain sorceries — which also read ``x_value`` but resolve to the
          graveyard and are out of this phase's scope — are never driven.
        * **kicker** — set when a CastingTimeOption annotation funding this cast
          carries a ``kickerAbilityGrpId``.

        Absent or ambiguous evidence leaves the card's defaults untouched: no X
        is invented (the creature honestly enters at 0/0 and dies), no kicker is
        assumed. Values live on the card object, which is the same instance the
        engine later resolves, so they survive to entry.
        """
        if not spell_iid:
            return

        # --- X evidence (entry-counter consumers only) ---
        mana_cost = getattr(card, "mana_cost", None)
        x_count = getattr(mana_cost, "x_count", 0) if mana_cost is not None else 0
        if (
            x_count > 0
            and hasattr(card, "x_value")
            and hasattr(card, "enters_battlefield_with")
        ):
            paid = self._count_cast_mana_paid(spell_iid, curr_snapshot)
            non_x = getattr(mana_cost, "cmc", 0)
            # cmc already excludes {X}; a clean nonnegative remainder that
            # divides evenly among the {X} symbols is the observed X.
            if paid >= non_x and (paid - non_x) % x_count == 0:
                x_value = (paid - non_x) // x_count
                if x_value > 0:
                    card.x_value = x_value

        # --- Kicker evidence (entry-counter consumers only) ---
        # Scoped to a permanent whose impl consumes entry counters
        # (``enters_battlefield_with``), so other kicker cards — whose kicker
        # option drives a graveyard return / extra land / team buff, out of this
        # phase's scope — are never switched on from replay evidence here.
        if (
            hasattr(card, "kicked")
            and hasattr(card, "enters_battlefield_with")
            and self._cast_declared_kicker(spell_iid, curr_snapshot)
        ):
            card.kicked = True

    def _count_cast_mana_paid(
        self, spell_iid: int, curr_snapshot: GameSnapshot
    ) -> int:
        """Count distinct ManaPaid annotations funding *spell_iid* (look-ahead).

        One ManaPaid annotation credits one mana (the executor's payment model),
        so the distinct-by-id count over the same look-ahead window used to
        credit the pool is the total mana spent on this cast.
        """
        start = self._gsid_index.get(curr_snapshot.game_state_id, 0)
        seen: set[int] = set()
        for snap in self.replay.snapshots[start : start + _ANNOTATION_LOOKAHEAD]:
            for ann in snap.annotations:
                if (
                    "AnnotationType_ManaPaid" in ann.type
                    and spell_iid in ann.affected_ids
                    and ann.id not in seen
                ):
                    seen.add(ann.id)
        return len(seen)

    def _cast_declared_kicker(
        self, spell_iid: int, curr_snapshot: GameSnapshot
    ) -> bool:
        """True if a CastingTimeOption funding *spell_iid* names a kicker.

        Arena tags a kicked cast with an ``AnnotationType_CastingTimeOption``
        whose details carry ``kickerAbilityGrpId``, keyed (via ``affectedIds``)
        to the cast's stack instance id.
        """
        start = self._gsid_index.get(curr_snapshot.game_state_id, 0)
        for snap in self.replay.snapshots[start : start + _ANNOTATION_LOOKAHEAD]:
            for ann in snap.annotations:
                if (
                    "AnnotationType_CastingTimeOption" in ann.type
                    and spell_iid in ann.affected_ids
                    and "kickerAbilityGrpId" in ann.details
                ):
                    return True
        return False

    @staticmethod
    def _parse_counter_annotation(ann: Any) -> tuple[bool, str, int] | None:
        """Decode a CounterAdded/Removed annotation to ``(is_add, name, amount)``.

        Returns ``None`` for a non-counter annotation, an unmapped counter type,
        or a non-positive amount (the real parser emits ``transaction_amount``
        and ``counter_type`` as either scalars or single-element lists).
        """
        is_add = "AnnotationType_CounterAdded" in ann.type
        is_remove = "AnnotationType_CounterRemoved" in ann.type
        if not (is_add or is_remove):
            return None
        ctype = ann.details.get("counter_type")
        if isinstance(ctype, list):
            ctype = ctype[0] if ctype else None
        amount = ann.details.get("transaction_amount")
        if isinstance(amount, list):
            amount = amount[0] if amount else None
        if not isinstance(amount, int) or amount <= 0:
            return None
        name = _gre_counter_name(ctype)
        if name is None:
            return None
        return is_add, name, amount

    def _resolve_counter_object(
        self, aid: int, snapshot: GameSnapshot | None = None
    ) -> Any:
        """The engine object for a GRE instance id, for counter reconciliation.

        Prefers the rebuilt instance map, then the token-correlation binding (an
        id-less minted token that first appears this snapshot is not yet in
        ``_engine_cards`` — that map is only rebuilt in the post-comparison
        resync). Finally, for a NON-token permanent that first appears this
        snapshot (also not yet in the map), it correlates same-snapshot by
        matching the GRE object's grpId to an unclaimed engine battlefield
        permanent. Landing the counter on its own snapshot (rather than deferring
        to the next) matters: a deferred counter lands one step after the resync
        has already installed an oracle P/T correction for the then-missing
        counter, and the two briefly double-count.

        The returned candidate is NOT yet proven — ``_engine_candidate_valid``
        must accept it before any fold (a stale ``_engine_cards`` binding may
        name an object that has since left the engine battlefield).
        """
        obj = self._engine_cards.get(aid)
        if obj is not None:
            return obj
        obj = self._counter_token_binding.get(aid)
        if obj is not None:
            return obj
        return self._match_new_battlefield_permanent(aid, snapshot)

    def _match_new_battlefield_permanent(
        self, aid: int, snapshot: GameSnapshot | None
    ) -> Any:
        """Match a not-yet-mapped GRE battlefield permanent to an unclaimed
        engine battlefield permanent of the same grpId (same-snapshot).

        Only a GRE object the snapshot itself places on the BATTLEFIELD may
        match (a graveyard/exile object with a battlefield twin's grpId must
        not steal the twin), and only among the permanents of the seat GRE
        says controls it (two same-grpId permanents across players must not
        cross-bind). Returns the engine object only when exactly one candidate
        is unclaimed (interchangeable duplicates or an ambiguous match stay
        deferred, so a counter is never guessed onto the wrong object).
        """
        if snapshot is None or self.game is None:
            return None
        gre_obj = snapshot.game_objects.get(aid)
        if gre_obj is None or not gre_obj.grp_id:
            return None
        if aid not in self._gre_battlefield_aids(snapshot):
            return None
        seat = gre_obj.controller_seat_id or gre_obj.owner_seat_id
        player = self.players.get(seat)
        if player is None:
            return None
        from engine.types import Zone

        claimed = {id(o) for o in self._engine_cards.values() if o is not None}
        claimed |= {id(o) for o in self._counter_token_binding.values()}
        candidates = [
            card
            for card in player.zones[Zone.BATTLEFIELD].get_all()
            if id(card) not in claimed
            and self._card_to_grp_id(card) == gre_obj.grp_id
        ]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _counter_key(obj: Any) -> tuple[Any, int]:
        """The stable ledger key for an engine object: ``(object_id, id(obj))``.

        ``object_id`` alone is NOT unique among live objects: copy-token card
        impls mint a token copy via ``copy.copy`` of the copied card, which
        skips ``__init__`` — the copy shares its original's ``object_id``, and
        both can sit on the battlefield at once (measured: a Stromkirk
        Bloodthief and its token copy, one key, two objects — the collision
        let one twin's epoch shadow the other's and falsely cancel a fold).
        ``id(obj)`` disambiguates live objects; every structure keyed this way
        pins its objects (the ledger via ``_ledger_obj``, pendency evidence
        via the payload's ``bf_pins``), so a key is never reused while it is
        still referenced.
        """
        return (getattr(obj, "object_id", None), id(obj))

    def _canonical_aid(self, aid: int) -> int:
        """The rename-chain ROOT of a GRE instance id.

        Follows the accumulated ObjectIdChanged links back to the earliest aid
        in the object's identity thread. An aid never renamed is its own root.
        The visited guard is purely defensive — instance ids are never reused,
        so a real stream cannot form a cycle.
        """
        seen: set[int] = set()
        while aid in self._counter_aid_alias and aid not in seen:
            seen.add(aid)
            aid = self._counter_aid_alias[aid]
        return aid

    def _canonical_counter_key(self, ann_id: int, aid: int) -> tuple[int, int]:
        """The canonical identity of one semantic counter effect."""
        return (ann_id, self._canonical_aid(aid))

    def _record_counter_aliases(self, renames: dict[int, int]) -> None:
        """Accumulate this snapshot's ObjectIdChanged links into the game-wide
        alias map (new aid -> the aid it renamed from).

        EVERY rename is recorded — including chains and renames across real
        zone transitions — because the map tracks GRE's identity THREAD, which
        is what makes a later persistent-slot repeat under the new aid the
        SAME semantic effect (it must hit the applied/cancelled record, never
        become a new effect). Whether a pending effect may CONTINUE across a
        hop is a separate, evidence-gated judgment.
        """
        for orig, new in renames.items():
            if new != orig:
                self._counter_aid_alias.setdefault(new, orig)

    def _object_zone_epoch(self, obj: Any) -> int:
        """The engine's monotonic zone-change count for ``obj`` — a pure read.

        ``refs.zone_epoch`` is advanced by ``move_to_zone`` (via
        ``note_zone_change``) on every real zone transition, so two equal reads
        bracket a window with NO transition, even when the object left and
        returned between them. Never calls ``refs.instance_id`` — no stint id
        is minted, no query-facing allocation is perturbed. Returns 0 when the
        registry is absent (bare test harnesses), where battlefield membership
        remains the sole retirement signal.
        """
        refs = getattr(self.game, "refs", None) if self.game is not None else None
        zone_epoch = getattr(refs, "zone_epoch", None)
        return zone_epoch(obj) if callable(zone_epoch) else 0

    def _engine_bf_stints(self) -> dict[tuple[Any, int], tuple[int, Any]]:
        """``counter key -> (zone epoch, object)`` for every permanent
        currently on the engine battlefield — one pure-read sweep per
        reconciliation pass.

        The key set is the battlefield-membership signal (retirement, candidate
        validation); the epoch values feed each pending effect's earliest-
        observation evidence (``bf_epochs``), which is what lets a later fold
        prove NO real zone transition happened during pendency. The object is
        carried so evidence recording can PIN it (a key must never be reused
        while evidence references it).
        """
        stints: dict[tuple[Any, int], tuple[int, Any]] = {}
        if self.game is None:
            return stints
        from engine.types import Zone

        for player in self.game.players:
            for card in player.zones[Zone.BATTLEFIELD].get_all():
                stints[self._counter_key(card)] = (self._object_zone_epoch(card), card)
        return stints

    def _update_pending_epoch_evidence(
        self, payload: dict[str, Any], bf_stints: dict[tuple[Any, int], tuple[int, Any]]
    ) -> None:
        """Record each engine battlefield object's ``(epoch, pass)`` at its
        EARLIEST observation during this effect's pendency (never overwritten).

        Recorded for ALL current battlefield objects — not just a resolved
        candidate — because the affected object is typically still
        uncorrelated while pending. This earliest-observation record serves
        PRE-WINDOW churn evidence (an anchored effect whose GRE identity is
        renamed before it was ever battlefield-attested — see
        ``_churn_proven_same_stint``) and the unresolved surface; the FOLD's
        continuity baseline is the frozen window-start census
        (``window_epochs``), not this record. Each newly observed object is
        PINNED (``bf_pins``) for the payload's lifetime so its counter key
        cannot be reused by a different object while evidence references it —
        window-census members are covered because the census is taken from
        the same sweep this method has just recorded.
        """
        known = payload.setdefault("bf_epochs", {})
        pins = payload.setdefault("bf_pins", [])
        for okey, (epoch, obj) in bf_stints.items():
            if okey not in known:
                known[okey] = (epoch, self._counter_recon_pass)
                pins.append(obj)

    @staticmethod
    def _gre_battlefield_aids(snapshot: GameSnapshot) -> set[int]:
        """Every instance id the snapshot places in a GRE battlefield zone."""
        return {
            iid
            for zone in snapshot.zones.values()
            if zone.type == "ZoneType_Battlefield"
            for iid in zone.object_instance_ids
        }

    def _seat_of_engine_player(self, player: Any) -> int | None:
        """The GRE seat controlling an engine Player (identity match)."""
        if player is None:
            return None
        for seat, candidate in self.players.items():
            if candidate is player:
                return seat
        return None

    def _apply_counter_annotations(self, snapshot: GameSnapshot) -> None:
        """Reconcile GRE CounterAdded/Removed state onto engine permanents.

        GRE objects carry no per-object counter field, so counter state is
        reconstructed from the annotation stream and written onto the correlated
        engine permanent as an authoritative SET before comparison — a counter
        the executor never fired (its source trigger didn't run in replay) still
        lands, while a counter the engine DID drive is not double-counted (the
        SET agrees) and its own trigger-driven counters are capped at the GRE
        total. Only what the GRE stream attests is ever written; nothing is
        fabricated.

        Identity is anchored to the engine object (its ``object_id``), which
        survives GRE instance-id churn; the battlefield STINT is
        (``object_id``, fold-time zone epoch). A ledger retires when its object
        leaves the engine battlefield OR its zone epoch advances — the epoch
        catches a leave-and-return completed entirely within one replay step
        (atomic blink), which end-of-step membership alone cannot. The SET is
        applied only when the ledger actually changed this snapshot (a fold), so
        the value persists via its ``_base_*`` shadow without being re-forced at
        every snapshot — re-forcing overrode the per-step oracle P/T resync at
        timing windows and reintroduced divergences. Each per-(annotation,
        affected id) effect is folded exactly once; an effect whose id is not
        yet correlated is deferred and retried under the expiration rules of
        ``_advance_pending_effect``, never silently dropped and never applied
        to a stint other than the one GRE attested. A deferred retry folds
        only onto a candidate present in the engine battlefield CENSUS taken
        on the pass GRE first attested the effect's identity on the
        battlefield (``battlefield_since``), with an unchanged zone epoch — a
        candidate first appearing after that window start carries no proof
        bracketing the window and cancels as unproven, no matter how many
        passes it waits (``_fold_counter_effect``).
        """
        from silverquillm.replay.state import extract_object_id_changes

        # One reconciliation pass per snapshot: the unit in which "observed on
        # an EARLIER pass" is judged for continuity evidence.
        self._counter_recon_pass += 1
        bf_stints = self._engine_bf_stints()
        # Retire counters for objects whose battlefield stint ended (departed,
        # or an epoch change proving an atomic leave-and-return). Runs before
        # folding so a counter re-attested this snapshot is not wiped.
        self._retire_departed_counters(set(bf_stints))
        gre_bf = self._gre_battlefield_aids(snapshot)
        renames = extract_object_id_changes(snapshot.annotations)
        # Extend the identity thread FIRST: an annotation later in this same
        # snapshot that names a renamed aid must already canonicalize to its
        # root (a repeat arriving in the rename's own snapshot is the same
        # semantic effect, not a new one).
        self._record_counter_aliases(renames)
        changed = False
        # Deferred effects: advance their GRE-side identity (proven-churn
        # re-keying / expiration), then retry the fold for the survivors.
        for key, payload in list(self._pending_counter_effects.items()):
            if self._advance_pending_effect(
                key, payload, snapshot, gre_bf, renames, bf_stints
            ):
                changed |= self._fold_counter_effect(
                    key, payload, snapshot, gre_bf, bf_stints
                )
        # Fold this snapshot's counter annotations.
        for ann in snapshot.annotations:
            parsed = self._parse_counter_annotation(ann)
            if parsed is None:
                continue
            is_add, name, amount = parsed
            for aid in ann.affected_ids:
                # Canonical identity: a repeat under any rename alias of the
                # affected aid is the SAME semantic effect as the original.
                key = self._canonical_counter_key(ann.id, aid)
                if (
                    key in self._applied_counter_effects
                    or key in self._cancelled_counter_effects
                ):
                    continue
                payload = self._pending_counter_effects.get(key)
                if payload is None:
                    payload = {
                        "name": name,
                        "is_add": is_add,
                        "amount": amount,
                        "current_aid": aid,
                        "ctx": None,
                        "seen_on_battlefield": False,
                        "pending_since": self._counter_recon_pass,
                        "battlefield_since": None,
                    }
                changed |= self._fold_counter_effect(
                    key, payload, snapshot, gre_bf, bf_stints
                )
        # Apply only when a fold changed the ledger — the SET persists via the
        # ``_base_*`` shadow, so re-forcing it every snapshot is unnecessary and
        # fights the oracle P/T resync at timing windows.
        if changed:
            self._reconcile_counters()

    def _retire_departed_counters(self, bf_keys: set[tuple[Any, int]]) -> None:
        """Retire every ledger whose battlefield stint has ended.

        A stint ends when the object is absent from the engine battlefield OR
        when its engine zone epoch has advanced past the fold-time value — the
        latter proves a real zone transition happened even though the object is
        back on the battlefield (atomic blink / bounce-and-replay within one
        replay step). Retirement clears the GRE-attested counters (and
        ``_base_*`` shadows) so a reused engine object cannot carry them into a
        new stint; newly attested counters for the returned stint then
        establish a fresh ledger."""
        for okey, obj in list(self._ledger_obj.items()):
            if (
                okey in bf_keys
                and self._object_zone_epoch(obj) == self._ledger_epoch.get(okey, 0)
            ):
                continue
            self._retire_ledger_entry(okey)

    def _retire_ledger_entry(self, okey: tuple[Any, int]) -> None:
        """Drop one object ledger and zero its GRE-attested counters."""
        obj = self._ledger_obj.pop(okey, None)
        stale = self._gre_counter_ledger.pop(okey, None)
        self._ledger_epoch.pop(okey, None)
        if obj is not None and stale:
            self._clear_engine_counters(obj, stale.keys())

    @staticmethod
    def _capture_counter_context(payload: dict[str, Any], gre_obj: Any) -> None:
        """Record the affected object's GRE identity the first time it is seen.

        The context (grpId + owner seat — both immutable for a GRE stint)
        proves that a later fold or churn re-key still targets the same object
        the annotation named. Controller is deliberately NOT part of identity
        continuity (control may change without ending a stint); it is checked
        against the ENGINE candidate at fold time instead.
        """
        if payload.get("ctx") is None:
            payload["ctx"] = {
                "grp_id": gre_obj.grp_id,
                "owner": gre_obj.owner_seat_id,
            }

    @staticmethod
    def _counter_context_matches(payload: dict[str, Any], gre_obj: Any) -> bool:
        """Whether ``gre_obj`` is identity-consistent with the recorded context.

        Only POSITIVE contradictions reject (both sides known and different) —
        an unknown grpId or seat is absence of evidence, not disagreement.
        """
        ctx = payload.get("ctx")
        if ctx is None:
            return True
        if ctx["grp_id"] and gre_obj.grp_id and ctx["grp_id"] != gre_obj.grp_id:
            return False
        return not (
            ctx["owner"]
            and gre_obj.owner_seat_id
            and ctx["owner"] != gre_obj.owner_seat_id
        )

    def _advance_pending_effect(
        self,
        key: tuple[int, int],
        payload: dict[str, Any],
        snapshot: GameSnapshot,
        gre_bf: set[int],
        renames: dict[int, int],
        bf_stints: dict[tuple[Any, int], tuple[int, Any]],
    ) -> bool:
        """Advance one pending effect's GRE-side identity for this snapshot.

        Returns ``True`` when the effect is still eligible for a fold attempt,
        ``False`` when it was cancelled. The expiration rules:

        1. The affected aid is present and identity-consistent — still
           eligible. (If it is present but NOT on the GRE battlefield: eligible
           only while it has never been on the battlefield during pendency —
           it may still be arriving, e.g. a stack resident; once it HAS been
           seen on the battlefield, leaving it ends the stint → cancel.)
        2. The aid is present but identity-INCONSISTENT with the recorded
           context (aid reuse) — the original stint is gone → cancel.
        3. The aid is absent but a SINGLE ObjectIdChanged hop renames it to an
           object that is on the GRE battlefield and identity-consistent —
           a churn CANDIDATE. GRE-side consistency alone cannot distinguish
           harmless id churn from a direct (or compressed) leave-and-return,
           so the effect continues ONLY when engine evidence positively proves
           the same battlefield stint: the effect has an anchored engine
           candidate (a prior resolved-and-validated correlation), that
           candidate is on the engine battlefield RIGHT NOW, and its epoch
           evidence obeys the window-start rule (``_churn_proven_same_stint``:
           present in the frozen window-start census with an unchanged epoch
           once GRE has battlefield-attested the identity; bracketed by a
           strictly earlier pendency observation before then). Anything
           less — no anchor, anchor departed, absent from the window-start
           census, epoch advanced — cancels: the effect is never applied
           speculatively, and the missing counter stays visible in
           comparison. A rename CHAIN (the target renamed again in the same
           snapshot) is a zone transit (blink legs), and a rename to a
           non-battlefield zone is a departure — both mean the stint ended →
           cancel.
        4. The aid is absent with no qualifying rename — the stint disappeared
           before correlation → cancel.

        A cancelled effect is recorded in ``_unresolved_counter_effects`` (the
        explicit unresolved-replay-limitation surface) and its canonical key in
        ``_cancelled_counter_effects`` — which every later lookup canonicalizes
        into, so a persistent-slot repeat under ANY rename alias can never
        re-enqueue or resurrect it. It is never applied late: the engine-side
        absence of the counter then surfaces as a normal compare divergence.
        """
        aid = payload["current_aid"]
        gre_obj = snapshot.game_objects.get(aid)
        if gre_obj is not None:
            if not self._counter_context_matches(payload, gre_obj):
                self._cancel_counter_effect(
                    key, payload, "affected id no longer matches its recorded identity"
                )
                return False
            if aid in gre_bf or not payload.get("seen_on_battlefield"):
                return True
            self._cancel_counter_effect(
                key, payload, "stint left the battlefield before correlation"
            )
            return False
        new_aid = renames.get(aid)
        if new_aid is not None and new_aid not in renames:
            new_obj = snapshot.game_objects.get(new_aid)
            if (
                new_obj is not None
                and new_aid in gre_bf
                and self._counter_context_matches(payload, new_obj)
            ):
                if self._churn_proven_same_stint(payload, bf_stints):
                    payload["current_aid"] = new_aid
                    return True
                self._cancel_counter_effect(
                    key,
                    payload,
                    "id change not provably same-stint churn (no engine "
                    "correlation evidence, or zone epoch advanced)",
                )
                return False
        self._cancel_counter_effect(
            key, payload, "affected object disappeared before correlation"
        )
        return False

    def _churn_proven_same_stint(
        self, payload: dict[str, Any], bf_stints: dict[tuple[Any, int], tuple[int, Any]]
    ) -> bool:
        """Whether engine evidence PROVES a GRE id change is same-stint churn.

        Requires the effect to be anchored to an engine candidate (positively
        correlated and validated while the GRE identity thread was intact)
        that is on the engine battlefield right now, plus continuity evidence
        obeying the same window-start rule as the fold:

        - Window OPEN (``battlefield_since`` set — GRE has attested the
          identity on the battlefield): the anchor must appear in the frozen
          window-start census with its current epoch equal to the census
          value. An anchor observed only after the window began cannot repair
          the missing start boundary — same rule as ``_fold_counter_effect``.
        - Window NOT yet open (the effect has only ever been observed off the
          battlefield — e.g. the annotation streams ahead of placement): the
          anchor's earliest pendency observation must come from an EARLIER
          reconciliation pass with its current epoch unchanged — bracketing
          the pre-window pendency. The fold that follows then opens the
          window and is immediate (zero-width), so no window gap is skipped.

        Either way, equal epochs prove no real zone transition (blink,
        bounce, death, reanimation) occurred in the bracketed interval, which
        mere GRE-side identity consistency cannot. Absence of any part of
        this evidence is absence of proof, never a pass.
        """
        anchor_okey = payload.get("anchor_okey")
        if anchor_okey is None:
            return False
        stint = bf_stints.get(anchor_okey)
        if stint is None:  # anchored object not on the engine bf now
            return False
        if payload.get("battlefield_since") is not None:
            window_base = payload.get("window_epochs", {}).get(anchor_okey)
            return window_base is not None and stint[0] == window_base
        observed = payload.get("bf_epochs", {}).get(anchor_okey)
        if observed is None:
            return False
        obs_epoch, obs_pass = observed
        return obs_pass < self._counter_recon_pass and stint[0] == obs_epoch

    def _cancel_counter_effect(
        self, key: tuple[int, int], payload: dict[str, Any], reason: str
    ) -> None:
        """Cancel a pending effect whose GRE stint ended before correlation."""
        self._pending_counter_effects.pop(key, None)
        self._cancelled_counter_effects.add(key)
        self._unresolved_counter_effects.append({
            "annotation_id": key[0],
            "affected_id": key[1],  # canonical (rename-chain root) aid
            "current_aid": payload.get("current_aid"),
            "name": payload.get("name"),
            "is_add": payload.get("is_add"),
            "amount": payload.get("amount"),
            "pending_since": payload.get("pending_since"),
            "battlefield_since": payload.get("battlefield_since"),
            "anchor_pass": payload.get("anchor_pass"),
            "reason": reason,
        })
        logger.debug(
            "counter effect (ann %d, aid %d) cancelled: %s", key[0], key[1], reason
        )

    def _engine_candidate_valid(
        self, obj: Any, gre_obj: Any, engine_bf: dict | set
    ) -> bool:
        """Whether the engine candidate provably IS the battlefield stint GRE
        attests for this effect.

        Requires the candidate to be on the engine battlefield RIGHT NOW —
        membership in ``engine_bf`` (the pass's ``_engine_bf_stints`` keys; a
        stale ``_engine_cards`` binding whose object departed is rejected) —
        and checks grpId, controller seat, and owner seat against the GRE
        object; only POSITIVE contradictions reject, so an id-less engine
        token or a bare test permanent without player attribution still folds.
        """
        if self._counter_key(obj) not in engine_bf:
            return False
        engine_grp = self._card_to_grp_id(obj)
        if engine_grp and gre_obj.grp_id and engine_grp != gre_obj.grp_id:
            return False
        controller_seat = self._seat_of_engine_player(getattr(obj, "controller", None))
        gre_controller = gre_obj.controller_seat_id or gre_obj.owner_seat_id
        if controller_seat is not None and gre_controller and controller_seat != gre_controller:
            return False
        owner_seat = self._seat_of_engine_player(getattr(obj, "owner", None))
        return not (
            owner_seat is not None
            and gre_obj.owner_seat_id
            and owner_seat != gre_obj.owner_seat_id
        )

    def _fold_counter_effect(
        self,
        key: tuple[int, int],
        payload: dict[str, Any],
        snapshot: GameSnapshot,
        gre_bf: set[int],
        bf_stints: dict[tuple[Any, int], tuple[int, Any]],
    ) -> bool:
        """Fold one canonical counter effect into the object ledger.

        Returns ``True`` if it modified the ledger (so the caller applies).
        Exactly-once per canonical key — a persistent-slot repeat (under the
        original aid or any rename alias) is a no-op, and a multi-id annotation
        whose ids correlate at different times applies each effect once. A fold
        happens only when the effect provably targets the SAME battlefield
        stint GRE attested for it:

        - GRE attests the affected object in THIS snapshot, on the battlefield,
          identity-consistent with the effect's recorded context;
        - the engine candidate is on the engine battlefield right now, with no
          grpId/controller/owner contradiction (``_engine_candidate_valid``);
        - the candidate does not contradict the effect's anchor (the engine
          object it was FIRST positively correlated to — a later re-binding to
          a different object is identity confusion → cancel, never a guess);
        - evidence brackets the COMPLETE relevant GRE battlefield window: the
          first pass on which GRE attests the effect's identity on the
          battlefield opens the window (``battlefield_since``) and freezes the
          engine battlefield census of that pass (``window_epochs``). The
          resolved candidate must appear in that census with its CURRENT zone
          epoch equal to the census value — proving it was on the engine
          battlefield at the window start and has not changed zones since. On
          the window-start pass itself any validated candidate satisfies this
          trivially (zero-width window — same-snapshot creation, token
          correlation, and an off-battlefield-observed effect whose GRE
          object and engine candidate arrive together all fold immediately).
          A candidate ABSENT from the census (created, resync-injected,
          returned, or renamed-in after the window began) is unproven FOREVER
          for this effect — advancing extra reconciliation passes never turns
          an after-boundary first observation into historical evidence, so it
          is cancelled, never folded speculatively. An epoch advanced past
          the census value proves a real zone transition happened during the
          window, so the returned stint must never receive the effect
          (cancel), regardless of whether GRE kept the aid, renamed it once,
          or renamed it through a chain.

        A GRE-side gap defers the effect (deduped by canonical key, retried
        under ``_advance_pending_effect``'s expiration rules) — never marked
        applied, never guessed onto an unproven object. Engine-side
        counter-evidence (anchor contradiction, missing prior observation,
        advanced epoch) CANCELS it — the missing counter then stays visible
        in comparison.
        """
        if key in self._applied_counter_effects:
            self._pending_counter_effects.pop(key, None)
            return False
        if key in self._cancelled_counter_effects:
            return False
        # The pass on which this effect was first processed opens its pendency
        # window (stamped at payload creation; the setdefault only covers
        # payloads handed in directly, and never advances an existing stamp).
        payload.setdefault("pending_since", self._counter_recon_pass)
        # Accumulate engine-side epoch evidence for this pendency window —
        # recorded for all current battlefield objects (the affected one is
        # typically still uncorrelated), BEFORE any defer/cancel branch.
        self._update_pending_epoch_evidence(payload, bf_stints)
        aid = payload["current_aid"]
        gre_obj = snapshot.game_objects.get(aid)
        if gre_obj is not None:
            self._capture_counter_context(payload, gre_obj)
            if self._counter_context_matches(payload, gre_obj):
                # Anchor the engine identity as early as possible — even when
                # the fold itself must defer (e.g. GRE has not yet listed the
                # aid on the battlefield): an already-correlated candidate that
                # validates NOW is the stint later churn proofs measure against.
                self._capture_counter_anchor(payload, gre_obj, bf_stints, snapshot)
        if (
            gre_obj is None
            or aid not in gre_bf
            or not self._counter_context_matches(payload, gre_obj)
        ):
            # GRE does not (yet) attest this stint on the battlefield — defer.
            self._pending_counter_effects[key] = payload
            return False
        payload["seen_on_battlefield"] = True
        if payload.get("battlefield_since") is None:
            # GRE attests this effect's identity on the battlefield for the
            # first time: open the relevant battlefield window and freeze the
            # engine battlefield census as its continuity baseline. (Census
            # members are pinned via bf_pins — the epoch-evidence update above
            # recorded this same sweep.)
            payload["battlefield_since"] = self._counter_recon_pass
            payload["window_epochs"] = {
                okey: epoch for okey, (epoch, _obj) in bf_stints.items()
            }
        obj = self._resolve_counter_object(aid, snapshot)
        anchor_obj = payload.get("anchor_obj")
        if anchor_obj is not None:
            if obj is not None and obj is not anchor_obj:
                # The aid re-bound to a DIFFERENT engine object than the one
                # this effect was anchored to: contradictory identity evidence.
                self._cancel_counter_effect(
                    key,
                    payload,
                    "affected id re-bound to a different engine object than "
                    "its anchored stint",
                )
                return False
            # A proven-churn re-key may leave the correlation maps without an
            # entry for the new aid until the next resync rebuild — the anchor
            # IS the resolution then (still validated below).
            obj = anchor_obj
        if obj is None or not self._engine_candidate_valid(obj, gre_obj, bf_stints):
            # No proven engine candidate — defer (deduped by key), retry later.
            self._pending_counter_effects[key] = payload
            return False
        okey = self._counter_key(obj)
        epoch = self._object_zone_epoch(obj)
        window_base = payload.get("window_epochs", {}).get(okey)
        if window_base is None:
            # The candidate was not on the engine battlefield when the GRE
            # battlefield window opened: whatever it is (created,
            # resync-injected, returned, or renamed-in after the boundary),
            # no evidence can bracket the window back to its start — and
            # waiting further passes can never create that evidence, because
            # the census is frozen. Never fold speculatively. (On the
            # window-start pass itself the census covers every current
            # battlefield resident, so a validated candidate is only absent
            # here when the window began earlier; a payload handed in without
            # a census fails closed.)
            self._cancel_counter_effect(
                key,
                payload,
                "candidate not on the engine battlefield at the start of the "
                "GRE battlefield window; same-stint continuity unproven",
            )
            return False
        if epoch != window_base:
            # The candidate changed zones after the window-start census (its
            # epoch advanced): the stint GRE attested is over, and a returned
            # stint must never receive the old effect.
            self._cancel_counter_effect(
                key, payload, "engine zone epoch advanced during the GRE "
                "battlefield window",
            )
            return False
        if anchor_obj is None:
            payload["anchor_obj"] = obj
            payload["anchor_okey"] = okey
            payload["anchor_pass"] = self._counter_recon_pass
        if okey in self._gre_counter_ledger and self._ledger_epoch.get(okey, 0) != epoch:
            # The existing ledger belongs to a previous battlefield stint of
            # this object — retire it before the new stint's first fold.
            self._retire_ledger_entry(okey)
        ledger = self._gre_counter_ledger.setdefault(okey, {})
        delta = payload["amount"] if payload["is_add"] else -payload["amount"]
        ledger[payload["name"]] = max(0, ledger.get(payload["name"], 0) + delta)
        self._ledger_obj[okey] = obj
        self._ledger_epoch[okey] = epoch
        self._applied_counter_effects.add(key)
        self._pending_counter_effects.pop(key, None)
        return True

    def _capture_counter_anchor(
        self,
        payload: dict[str, Any],
        gre_obj: Any,
        bf_stints: dict[tuple[Any, int], tuple[int, Any]],
        snapshot: GameSnapshot,
    ) -> None:
        """Pin the effect's ENGINE identity at its first positive correlation.

        The anchor is the engine object the affected aid resolves to while the
        GRE identity thread is intact AND the candidate validates (on the
        engine battlefield, no grpId/controller/owner contradiction). It is
        what a later churn proof or fold measures continuity against; it is
        captured at most once and never replaced — a later contradicting
        resolution cancels the effect instead (``_fold_counter_effect``).
        """
        if payload.get("anchor_obj") is not None:
            return
        cand = self._resolve_counter_object(payload["current_aid"], snapshot)
        if cand is not None and self._engine_candidate_valid(cand, gre_obj, bf_stints):
            payload["anchor_obj"] = cand
            payload["anchor_okey"] = self._counter_key(cand)
            payload["anchor_pass"] = self._counter_recon_pass

    def _reconcile_counters(self) -> None:
        """Write every surviving object ledger onto its engine permanent as an
        authoritative SET (capping the engine's own trigger-driven counters at
        the GRE total)."""
        for okey, ledger in self._gre_counter_ledger.items():
            obj = self._ledger_obj.get(okey)
            if obj is not None:
                self._write_engine_counters(obj, ledger)

    @staticmethod
    def _write_engine_counters(obj: Any, ledger: dict[str, int]) -> None:
        """SET ``obj``'s counters to the ledger totals (with ``_base_*`` shadows).

        ``+1/+1`` / ``-1/-1`` write both the live field and its ``_base_*``
        shadow so the value survives ``apply_all``'s reset-then-reapply; other
        counter types live in ``_generic_counters``, which already persists
        across characteristic resets.
        """
        for name, total in ledger.items():
            if name == "+1/+1" and hasattr(obj, "plus_one_counters"):
                obj.plus_one_counters = total
                if hasattr(obj, "_base_plus_one_counters"):
                    obj._base_plus_one_counters = total
            elif name == "-1/-1" and hasattr(obj, "minus_one_counters"):
                obj.minus_one_counters = total
                if hasattr(obj, "_base_minus_one_counters"):
                    obj._base_minus_one_counters = total
            else:
                store = getattr(obj, "_generic_counters", None)
                if store is None:
                    store = {}
                    obj._generic_counters = store
                store[name] = total

    @staticmethod
    def _clear_engine_counters(obj: Any, names: Any) -> None:
        """Zero the GRE-attested counters ``names`` on ``obj`` (with shadows).

        Called on stint retirement so a reused engine object cannot carry a
        prior stint's counters into a new one. Only the named (previously
        GRE-attested) counters are cleared — nothing else is disturbed.
        """
        for name in names:
            if name == "+1/+1":
                if hasattr(obj, "plus_one_counters"):
                    obj.plus_one_counters = 0
                if hasattr(obj, "_base_plus_one_counters"):
                    obj._base_plus_one_counters = 0
            elif name == "-1/-1":
                if hasattr(obj, "minus_one_counters"):
                    obj.minus_one_counters = 0
                if hasattr(obj, "_base_minus_one_counters"):
                    obj._base_minus_one_counters = 0
            else:
                store = getattr(obj, "_generic_counters", None)
                if isinstance(store, dict):
                    store.pop(name, None)

    def _take_from_hand(self, player: Any, action: ReplayAction, snapshot: GameSnapshot) -> Any:
        """Find the acted-on card in *player*'s engine hand, materializing it.

        A hidden-hand shell (opponent hand, undrawn identity) is replaced by
        the real card the moment GRE reveals it through an action — so both
        seats' plays run through real implementations.
        """
        from engine.types import Zone

        hand = player.zones[Zone.HAND]
        card = self._find_card_by_grp_id(hand.get_all(), action.grp_id)
        if card is None:
            card = self._find_card_by_name(hand.get_all(), action.card_name)
        if card is not None:
            return card

        # Materialize: replace an identity-less shell (or conjure the card
        # if the engine hand has drifted below the GRE hand).
        shells = [c for c in hand.get_all() if self._card_to_grp_id(c) == 0]
        if shells:
            hand.remove(shells[0])
        obj = snapshot.game_objects.get(action.instance_id)
        if obj is not None and obj.grp_id:
            card = self._create_card_from_object(obj, player)
        else:
            card = self._create_card(action.grp_id, player)
            card._grp_id = action.grp_id
        hand.add(card)
        return card

    def _derive_target_preferences(
        self,
        seat: int,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        spell_iid: int = 0,
    ) -> tuple[Any, ...]:
        """Build intent preferences from GRE TargetSpec annotations.

        TargetSpec (a persistent annotation) is the spell-scoped record of
        chosen targets: ``affectorId`` is the targeting spell/ability
        instance id and ``affectedIds`` are the chosen targets (object
        instance ids, or seat ids for player targets), with an ``index``
        detail ordering multi-target spells. Keying on the spell id makes
        cross-wiring with another same-seat targeted object impossible.
        (PlayerSubmittedTargets is NOT usable here: its affectedIds name the
        submitting spell, not the targets.)

        Each target maps to the correlated engine object (bound by the
        engine-minted instance id, the one dynamically-bound field) or an
        engine player (bound by seat). A name-based preference follows as a
        fallback when no engine instance id is available, and the greedy
        preference scan takes the first that matches an offered option. No
        TargetSpec found (or no spell id) yields no preferences — the
        permissive baseline answers, and compare-first records any wrong
        guess.
        """
        from engine.decisions import Decision

        if not spell_iid:
            return ()

        # TargetSpec streams a couple of snapshots after the cast event
        # (like ManaPaid) — scan forward; it persists once present, and the
        # affector filter is exact because instance ids are never reused.
        entries: list[tuple[int, int]] = []  # (index, target id)
        seen: set[int] = set()
        candidates: list[GameSnapshot] = [prev_snapshot]
        start = self._gsid_index.get(curr_snapshot.game_state_id)
        if start is not None:
            candidates.extend(
                self.replay.snapshots[start : start + _ANNOTATION_LOOKAHEAD]
            )
        else:
            candidates.append(curr_snapshot)
        for snap in candidates:
            anns = list(snap.annotations) + list(snap.persistent_annotations.values())
            for ann in anns:
                if (
                    "AnnotationType_TargetSpec" not in ann.type
                    or ann.affector_id != spell_iid
                    or ann.id in seen
                ):
                    continue
                seen.add(ann.id)
                index = ann.details.get("index", 0)
                if isinstance(index, list):
                    index = index[0] if index else 0
                for tid in ann.affected_ids:
                    entries.append((index, tid))
            if entries:
                break

        preferences: list[Any] = []
        for _, tid in sorted(entries, key=lambda e: e[0]):
            if tid in self.players:
                preferences.append(Decision.player(seat=tid))
                continue
            # A target that is a pending spell binds to its exact StackObject
            # occurrence: Zone.STACK target queries offer occurrences (not
            # source cards), so the preference must name the occurrence's own
            # minted instance id — a card-stint or name preference could match
            # a different cast/copy of the same card.
            so = self._pending_stack_objs.get(tid)
            if so is not None and self._occurrence_on_stack(so):
                occ_iid = self._stack_occurrence_instance_id(so)
                if occ_iid is not None:
                    preferences.append(Decision.obj(instance=occ_iid))
                    continue
            target = self._engine_cards.get(tid)
            if target is None:
                continue
            engine_iid = self._engine_instance_id(target)
            if engine_iid is not None:
                preferences.append(Decision.obj(instance=engine_iid))
            elif getattr(target, "name", ""):
                preferences.append(Decision.obj(name=target.name))
        return tuple(preferences)

    def _engine_instance_id(self, card: Any) -> int | None:
        """The engine-minted instance id for *card* in its current zone."""
        if self.game is None or not hasattr(self.game, "refs"):
            return None
        from engine.types import Zone

        for player in self.game.players:
            for zone in Zone:
                if player.zones[zone].contains(card):
                    return self.game.refs.instance_id(card, zone)
        return None

    def _stack_occurrence_instance_id(self, stack_obj: Any) -> int | None:
        """The engine-minted instance id of a StackObject occurrence itself.

        Matches the id the engine's Zone.STACK target enumeration mints for the
        occurrence (``refs.instance_id(stack_obj, "stack")``), so a preference
        built here selects exactly that occurrence among the offered options.
        ``None`` for an engine without a refs registry.
        """
        if self.game is None or not hasattr(self.game, "refs"):
            return None
        from engine.types import Zone

        return self.game.refs.instance_id(stack_obj, Zone.STACK.value)

    def _simulate_spell_cast(
        self,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Cast a spell through the engine, answering its queries from GRE.

        Targets observed in the replay become an Intent on the casting
        player (routed by the card's printed name); mana was already
        credited by _apply_mana_payments. On CastingError the failure is
        recorded and the spell falls back to oracle placement so the game
        can continue.
        """
        from engine.casting import cast_spell
        from engine.decisions import GameRef
        from engine.intent_player import Intent
        from engine.types import Zone

        player = self.players.get(action.player_seat_id)
        if player is None or self.game is None:
            result.infra_failures.append(
                f"cast_spell {action.card_name}: no engine player for seat "
                f"{action.player_seat_id}"
            )
            return

        card = self._take_from_hand(player, action, curr_snapshot)
        self._apply_spell_mana_lookahead(action.instance_id, curr_snapshot)
        # Supply cast-time evidence (chosen X, kicker) to the enters-with-counters
        # primitive BEFORE the spell is cast, so the counters land as it enters.
        self._apply_cast_time_evidence(card, action.instance_id, curr_snapshot)
        preferences = self._derive_target_preferences(
            action.player_seat_id, prev_snapshot, curr_snapshot,
            spell_iid=action.instance_id,
        )
        intent_name = f"replay_cast_{action.instance_id}"
        has_intents = hasattr(player, "start_intent")
        if has_intents:
            player.start_intent(intent_name, Intent(
                pattern=GameRef(card=frozenset({("name", card.name)})),
                preferences=preferences,
            ))
        stack_obj = None
        try:
            stack_obj = cast_spell(self.game, player, card)
        except Exception as exc:
            result.engine_failures.append(
                f"cast_spell {action.card_name} (seat {action.player_seat_id}): "
                f"{type(exc).__name__}: {exc}"
            )
            # Oracle fallback: place it on the engine stack so resolution
            # timing still mirrors GRE (resolved on the stack-exit action).
            hand = player.zones[Zone.HAND]
            if hand.contains(card):
                hand.remove(card)
            if not player.zones[Zone.STACK].contains(card):
                player.zones[Zone.STACK].add(card)
        finally:
            if has_intents:
                # No postcondition: state comparison is the arbiter.
                player.end_intent(intent_name)

        if action.instance_id:
            self._engine_cards[action.instance_id] = card
            self._pending_stack[action.instance_id] = card
            self._record_pending_occurrence(action.instance_id, card, stack_obj)

    def _resolve_stack_object_for(self, card: Any) -> bool:
        """Resolve the engine StackObject whose source is *card*, if any."""
        if self.game is None:
            return False
        stack_obj = self.game.stack.pop_by_source(card)
        if stack_obj is None:
            return False
        stack_obj.on_resolve(self.game)
        return True

    def _record_pending_occurrence(
        self, gre_iid: int, card: Any, stack_obj: Any
    ) -> None:
        """Retain the exact StackObject pushed for a driven cast under *gre_iid*.

        *stack_obj* is the cast helper's return value. An engine whose cast
        helpers predate the occurrence return (the frozen SOS workspace)
        returns ``None`` — then recover the occurrence as the topmost stack
        object sourced by *card*, which immediately after THIS executor's own
        cast call is unambiguous (the spell is pushed last; anything a cast
        trigger pushed sits below it). If none exists (oracle-fallback cast:
        the card sits in a stack zone with no StackObject), no occurrence is
        recorded and the occurrence-gated paths (arrival resolution, exact
        stack-exit resolution, stack-target preferences) never fire for this
        id — the resync reconciles instead.
        """
        game = self.game
        if stack_obj is None and game is not None:
            stack_obj = next(
                (
                    o
                    for o in reversed(game.stack._items)
                    if getattr(o, "source", None) is card
                ),
                None,
            )
        if stack_obj is not None:
            self._pending_stack_objs[gre_iid] = stack_obj

    def _occurrence_on_stack(self, stack_obj: Any) -> bool:
        """True iff exactly *stack_obj* is on the engine stack, by identity.

        Never by equality (StackObject is a field-compared dataclass) and never
        by source card (a trigger may share the card; copies/recasts mint new
        occurrences).
        """
        game = self.game
        if game is None or stack_obj is None:
            return False
        return any(item is stack_obj for item in game.stack._items)

    def _resolve_arrived_spells(
        self, snapshot: GameSnapshot, result: StepResult
    ) -> None:
        """Resolve pending engine spells GRE already attests on the battlefield.

        The executor drives ``cast_spell`` at the cast event; the engine spell
        then sits on the engine stack until GRE reports its resolution. For a
        permanent spell GRE frequently resolves it SILENTLY — the card appears in
        the battlefield zone listing with no ObjectIdChanged and no action — so
        ``infer_actions`` produces nothing and the pending object would resolve
        only in this step's post-comparison resync flush, one snapshot after GRE
        showed the permanent. That one-snapshot skew is the dominant divergence
        family: a ``zone_contents`` battlefield ``snapshot_extra`` that
        self-corrects the very next snapshot.

        The trigger is strict, evidence-aligned GRE attestation of the exact
        occurrence: the top of the engine stack is resolved only when it IS a
        retained pending-spell StackObject (``_pending_stack_objs`` — identity,
        never ``top.source``: a triggered ability may share its source card
        with the spell, and copies/recasts mint new occurrences of it) AND the
        CURRENT snapshot lists that occurrence's object on a battlefield (by
        the id it was cast under, or that id's ObjectIdChanged successor this
        snapshot). No attestation → the object stays pending and the divergence
        stands honestly (a countered/fizzled spell GRE never places on the
        battlefield is never speculatively resolved here).

        Stack order is respected: only the top of the engine stack is resolved,
        and the loop stops at the first top that is not an attested pending
        spell, so nothing is ever resolved out from under an object above it.
        In the common case the engine stack holds exactly the one just-cast
        spell. An ETB effect the resolution registers (a trigger pushed onto
        the stack, an enters-with counter) is left for its own machinery — a
        newly pushed trigger is not in the pending-occurrence map (even though
        its ``source`` is the just-resolved card), so the loop halts on it and
        the trigger resolves only when its own GRE evidence (an
        ``ability_resolution`` action or the resync flush) drives it.
        """
        game = self.game
        if game is None or game.stack.is_empty():
            return
        from silverquillm.replay.state import extract_object_id_changes

        bf_ids = self._gre_battlefield_aids(snapshot)
        id_changes = extract_object_id_changes(snapshot.annotations)

        # Reverse map each pending OCCURRENCE to the GRE id(s) it was cast
        # under, so the top of the stack can be recognized as a specific
        # pending spell (id(...) keys are safe: the map holds the references).
        occurrence_gre_ids: dict[int, set[int]] = {}
        for gre_id, so in self._pending_stack_objs.items():
            if so is not None:
                occurrence_gre_ids.setdefault(id(so), set()).add(gre_id)

        def attested(gids: set[int]) -> bool:
            for gid in gids:
                if gid in bf_ids:
                    return True
                succ = id_changes.get(gid)
                if succ is not None and succ in bf_ids:
                    return True
            return False

        guard = 0
        while not game.stack.is_empty() and guard < 50:
            guard += 1
            top = game.stack.peek()
            gids = occurrence_gre_ids.get(id(top), set())
            if not gids or not attested(gids):
                # Respect stack order — stop at the first top that is not an
                # attested pending spell (an unattested spell, or any object
                # that is not a pending cast occurrence at all: a trigger, an
                # ability, a copy the executor did not cast).
                break
            card = getattr(top, "source", None)
            game.stack.pop()
            try:
                top.on_resolve(game)
            except Exception as exc:
                if _is_protocol_exception(exc):
                    raise
                result.engine_failures.append(
                    f"arrival resolution {getattr(card, 'name', '?')}: "
                    f"{type(exc).__name__}: {exc}"
                )
            # The pending occurrence is now resolved: drop it from both pending
            # maps and point _engine_cards at the resolved card under every id
            # it was known by (including the battlefield id it may have changed
            # into).
            for gid in gids:
                self._pending_stack.pop(gid, None)
                self._pending_stack_objs.pop(gid, None)
                self._engine_cards[gid] = card
                succ = id_changes.get(gid)
                if succ is not None:
                    self._engine_cards[succ] = card

    def _simulate_zone_transition(
        self,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Drive a generic GRE zone move through the engine.

        Stack exits resolve the engine's pending StackObject (real spell
        resolution); other moves go through move_to_zone so leave/enter
        triggers fire. Unmapped objects fall through to the resync.
        """
        from engine.types import Zone
        from silverquillm.replay.state import extract_object_id_changes

        id_changes = extract_object_id_changes(curr_snapshot.annotations)
        orig_iid = next(
            (o for o, n in id_changes.items() if n == action.instance_id), None
        )
        card = None
        stack_obj = None
        if orig_iid is not None:
            card = self._pending_stack.pop(orig_iid, None) or self._engine_cards.get(orig_iid)
            stack_obj = self._pending_stack_objs.pop(orig_iid, None)
        if card is None:
            card = self._pending_stack.pop(action.instance_id, None) or self._engine_cards.get(action.instance_id)
        if stack_obj is None:
            stack_obj = self._pending_stack_objs.pop(action.instance_id, None)

        if (
            action.dest_zone == "ZoneType_Stack"
            and action.source_zone in ("ZoneType_Graveyard", "ZoneType_Exile")
            and card is not None
        ):
            # Cast from a non-hand zone (flashback and similar): a real
            # cast, not a bare zone move — the mana was already paid via
            # ManaPaid annotations, so the free-cast path (which skips
            # payment but keeps legality, targeting, and resolution) is
            # the faithful route.
            self._simulate_noncast_zone_cast(action, prev_snapshot, curr_snapshot, card, result)
            return

        if action.source_zone == "ZoneType_Stack" and card is not None:
            # Spell resolution — run the queued engine resolution if present.
            # Prefer the exact retained occurrence for this GRE id: popping by
            # source card would be ambiguous when the card is shared (a pending
            # trigger, a copy, a recast under another id). Fall back to
            # pop_by_source only when no occurrence was retained (oracle
            # fallback) or it already left the stack (arrival-resolved earlier
            # this step — then no same-source object should be consumed here).
            try:
                if stack_obj is not None:
                    items = self.game.stack._items
                    idx = next(
                        (i for i, item in enumerate(items) if item is stack_obj),
                        None,
                    )
                    if idx is not None:
                        items.pop(idx)
                        stack_obj.on_resolve(self.game)
                    # else: the exact occurrence already departed (resolved or
                    # countered earlier); its card needs no zone move here.
                    resolved = True
                else:
                    resolved = self._resolve_stack_object_for(card)
            except Exception as exc:
                # Per-action failure, not a step abort (audit: this was the
                # second unguarded on_resolve site). The stack object was
                # already consumed; the resync reconciles the fallout.
                if _is_protocol_exception(exc):
                    raise
                result.engine_failures.append(
                    f"resolve {action.card_name} (stack exit): "
                    f"{type(exc).__name__}: {exc}"
                )
                resolved = True
            if resolved:
                if action.instance_id:
                    self._engine_cards[action.instance_id] = card
                return
            # Oracle-placed cast (failed cast_spell): move it manually.

        src = _GRE_ZONE_TO_ENGINE.get(action.source_zone)
        dst = _GRE_ZONE_TO_ENGINE.get(action.dest_zone)
        if card is None or src is None or dst is None:
            return  # resync will reconcile

        try:
            from engine.zones import move_to_zone
            move_to_zone(self.game, card, Zone(src), Zone(dst))
        except Exception as exc:
            result.engine_failures.append(
                f"move_to_zone {action.card_name} "
                f"({action.source_zone}->{action.dest_zone}): "
                f"{type(exc).__name__}: {exc}"
            )
            return
        if action.instance_id:
            self._engine_cards[action.instance_id] = card

    def _simulate_noncast_zone_cast(
        self,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        card: Any,
        result: StepResult,
    ) -> None:
        """Cast *card* from a non-hand zone (flashback etc.) via free-cast."""
        from engine.casting import cast_spell_free
        from engine.types import Zone

        try:
            from engine.casting import CastMode
        except ImportError:
            # Engine without explicit cast modes (the frozen SOS workspace):
            # cast without a mode — that engine has no flashback disposition.
            CastMode = None

        player = self.players.get(action.player_seat_id) or getattr(card, "owner", None)
        if player is None or self.game is None:
            return
        src = _GRE_ZONE_TO_ENGINE.get(action.source_zone)
        # Select the cast mode explicitly: the GRE stream attests a
        # graveyard->stack cast and the card's own flashback cost attests the
        # capability, which together identify a flashback cast (its later
        # graveyard->exile transition confirms it). The engine's generic
        # free-cast helper never infers this; the executor must state it.
        cast_kwargs: dict[str, Any] = {}
        if (
            CastMode is not None
            and src is not None
            and Zone(src) is Zone.GRAVEYARD
            and getattr(card, "flashback_cost", None) is not None
        ):
            cast_kwargs["mode"] = CastMode.FLASHBACK
        try:
            stack_obj = self._with_target_intent(
                action, prev_snapshot, curr_snapshot,
                lambda: cast_spell_free(
                    self.game, player, card, Zone(src), **cast_kwargs
                ),
            )
        except Exception as exc:
            result.engine_failures.append(
                f"cast_spell_free {action.card_name} "
                f"(from {action.source_zone}, seat {action.player_seat_id}): "
                f"{type(exc).__name__}: {exc}"
            )
            return
        if action.instance_id:
            self._engine_cards[action.instance_id] = card
            self._pending_stack[action.instance_id] = card
            self._record_pending_occurrence(action.instance_id, card, stack_obj)

    def _simulate_ability_resolution(
        self,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Drive an ability through the engine as GRE reports it.

        Activation: fund the ability's mana cost by look-ahead (ManaPaid
        annotations reference the ability's instance id, like spells), then
        — if the engine didn't already queue a matching trigger for the
        source — activate the source's activated ability through
        activate_ability, which pays costs (tapping the source for {T})
        and pushes the effect onto the engine stack.

        Resolution: pop and resolve the pending StackObject for the source,
        answering its targeting queries from PlayerSubmittedTargets. A
        missed effect shows up in the state comparison, not as a patched
        value.
        """
        if action.action_type == "ability_activation":
            self._apply_spell_mana_lookahead(action.instance_id, curr_snapshot)
            source_card = self._find_ability_source(action)
            player = self.players.get(action.player_seat_id)
            if (
                source_card is not None
                and player is not None
                and not self._stack_has_source(source_card)
            ):
                self._try_activate_ability(
                    player, source_card, action, prev_snapshot, curr_snapshot, result
                )
            if action.instance_id in curr_snapshot.game_objects:
                return  # still on the GRE stack; resolve when it leaves
            # created and resolved within one diff — resolve immediately

        source_card = self._find_ability_source(action)
        if source_card is not None:
            name = action.card_name or getattr(source_card, "name", "?")
            try:
                self._with_target_intent(
                    action, prev_snapshot, curr_snapshot,
                    lambda: self._resolve_stack_object_for(source_card),
                )
            except Exception as exc:
                # A card crash is a per-action failure, never a step abort:
                # the step's remaining actions, comparisons, and resync
                # still run. Protocol exceptions surface per contract.
                if _is_protocol_exception(exc):
                    raise
                result.engine_failures.append(
                    f"ability_resolution {name} (seat {action.player_seat_id}): "
                    f"{type(exc).__name__}: {exc}"
                )

    def _stack_has_source(self, card: Any) -> bool:
        """True if the engine stack already holds an object from *card*."""
        return self.game is not None and self.game.stack.has_source(card)

    @contextmanager
    def _replay_activation_context(self, player: Any):
        """Supply the observed-legal timing GRE confirms for a driven activation.

        GRE is ground truth that an observed activation was legal, but the
        snapshot's ``turn_info`` phase can lag the actual activation moment —
        Arena routinely reports a combat step for a main-phase equip — which
        makes the engine's sorcery-speed ``can_activate`` gate (equip, loyalty)
        reject a legal activation as "illegal (timing or zone)". For the
        duration of a driven activation ONLY, this aligns the engine to a
        sorcery-legal context: the active player is the activator and the phase
        is a main phase. The gate still runs in full (source zone, control,
        authorization are all still checked) — it is never weakened; it is
        simply given the observed-legal timing. Engine/non-replay activation is
        untouched (this is executor-owned), so Phase C's gate stays strict
        there. State is saved and restored so nothing leaks into comparison.
        """
        game = self.game
        if game is None:
            yield
            return
        from engine.types import Phase

        saved_phase = getattr(game, "phase", None)
        saved_idx = getattr(game, "active_player_index", None)
        try:
            for i, seat in enumerate(sorted(self.players.keys())):
                if self.players[seat] is player:
                    game.active_player_index = i
                    break
            if saved_phase not in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN):
                game.phase = Phase.PRECOMBAT_MAIN
            yield
        finally:
            if saved_phase is not None:
                game.phase = saved_phase
            if saved_idx is not None:
                game.active_player_index = saved_idx

    def _try_activate_ability(
        self,
        player: Any,
        source_card: Any,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Activate *source_card*'s activated ability, driving it when unambiguous.

        The single-ability case is driven directly. For a **multi-ability**
        source, the exact ability is not recoverable from the stream alone: GRE
        ability objects carry an ability grpId, but there is no per-card map from
        that grpId to a specific engine ability, and ``ActivatedAbility.cost`` is
        an opaque, side-effecting callable that cannot be dry-run to select by
        cost-payability. Phase M adds the evidence-based path sanctioned by #40:
        each ability may expose a pure ``predicted_outcome(game, source)``
        declaring its effect on the compared surfaces; the executor drives an
        ability only when **exactly one** candidate's prediction matches the
        observed prev->curr GRE delta (:meth:`_disambiguate_multi_ability`).

        A tie (>=2 predictions match), an empty match set, or a source with no
        predictions falls through to the resync — recording the real divergence
        via state comparison rather than guessing — and marks the source
        ``ambiguous`` so its surviving mismatches are attributed to the
        stream-limitation floor. Zero-ability sources here are triggered
        abilities the parser labeled ``ability_activation``; the resolution path
        (or resync) handles them.
        """
        try:
            abilities = list(source_card.get_activated_abilities() or [])
        except Exception:
            abilities = []
        if not abilities:
            return
        if len(abilities) == 1:
            chosen = abilities[0]
        else:
            chosen = self._disambiguate_multi_ability(
                source_card, abilities, prev_snapshot, curr_snapshot
            )
            if chosen is None:
                # Ambiguity residue: refuse to guess. Record the source so the
                # validation layer tags its mismatches as an attributed
                # stream limitation, then fall through to the resync.
                self._ambiguous_sources.add(getattr(source_card, "name", "?"))
                return
        from engine.abilities import ActivatedAbilityInstance, activate_ability

        instance = ActivatedAbilityInstance(
            source=source_card,
            controller=player,
            cost=chosen.cost,
            effect=chosen.effect,
            is_mana_ability=False,
            description=chosen.description,
            targeting=getattr(chosen, "targeting", None),
            can_activate=getattr(chosen, "can_activate", None),
        )
        name = action.card_name or getattr(source_card, "name", "?")
        try:
            with self._replay_activation_context(player):
                self._with_target_intent(
                    action, prev_snapshot, curr_snapshot,
                    lambda: activate_ability(self.game, player, instance),
                )
        except Exception as exc:
            result.engine_failures.append(
                f"activate_ability {name} (seat {action.player_seat_id}): "
                f"{type(exc).__name__}: {exc}"
            )

    def _disambiguate_multi_ability(
        self,
        source_card: Any,
        abilities: list[Any],
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
    ) -> Any | None:
        """Select the one ability whose prediction matches the observed delta.

        Evaluates each candidate's pure ``predicted_outcome(game, source)``
        against the observed prev->curr GRE delta for *source_card*. Returns the
        unique matching :class:`~engine.card.ActivatedAbility`, or ``None`` when
        the choice is not uniquely evidenced (no predictions, an ability without
        a prediction hook, a tie, or an empty match set) — the honest
        fall-through. Never mutates game state; predictions are read-only.
        """
        # Every candidate must expose a prediction hook, else we cannot compare
        # like with like — refuse rather than partially guess.
        predictors = [getattr(a, "predicted_outcome", None) for a in abilities]
        if any(p is None for p in predictors):
            return None
        observed = self._observed_source_delta(
            source_card, prev_snapshot, curr_snapshot
        )
        if observed is None:
            return None
        matches: list[Any] = []
        for ability, predict in zip(abilities, predictors):
            try:
                prediction = predict(self.game, source_card)
            except Exception:  # noqa: BLE001 — a raising predictor is not trustworthy evidence
                return None
            if prediction is None:
                continue  # ability not currently applicable
            if self._prediction_matches(prediction, source_card, observed):
                matches.append(ability)
        return matches[0] if len(matches) == 1 else None

    def _observed_source_delta(
        self, source_card: Any, prev: GameSnapshot, curr: GameSnapshot
    ) -> dict[str, Any] | None:
        """Read the GRE prev->curr delta for *source_card* on compared surfaces.

        Returns a dict describing what GRE observed happened around this source
        — whether it left the battlefield, its resulting P/T, and each player's
        life delta — or ``None`` when the source cannot be located in the GRE
        stream (no evidence to match against). Pure: reads snapshots only.
        """
        gre_iid = next(
            (iid for iid, c in self._engine_cards.items() if c is source_card),
            None,
        )
        if gre_iid is None:
            return None

        def _on_battlefield(snap: GameSnapshot, iid: int) -> bool:
            obj = snap.game_objects.get(iid)
            if obj is None:
                return False
            zone = snap.zones.get(obj.zone_id)
            return bool(zone and zone.type == "ZoneType_Battlefield")

        source_prev_bf = _on_battlefield(prev, gre_iid)
        source_curr_bf = _on_battlefield(curr, gre_iid)
        curr_obj = curr.game_objects.get(gre_iid)
        curr_pt = (
            (curr_obj.power, curr_obj.toughness)
            if curr_obj is not None
            and curr_obj.power is not None
            and curr_obj.toughness is not None
            else None
        )
        life_deltas = {
            seat: curr.get_player_life(seat) - prev.get_player_life(seat)
            for seat in curr.players
            if seat in prev.players
        }
        return {
            "source_left_bf": source_prev_bf and not source_curr_bf,
            "source_present": source_prev_bf,
            "source_curr_pt": curr_pt,
            "life_deltas": life_deltas,
        }

    def _prediction_matches(
        self, prediction: Any, source_card: Any, observed: dict[str, Any]
    ) -> bool:
        """True when *prediction* is consistent with the observed GRE delta.

        Checks the discriminating compared surfaces: whether the source leaves
        the battlefield (decisive — every activated ability at least involves its
        source, so a predicted leave that did not happen, or a stay that did,
        rules the candidate out), the source's resulting P/T if the ability sets
        it, and the sign of any predicted opponent life loss. Extra observed
        changes (from unrelated same-snapshot effects) never disqualify a
        candidate — only contradicted predictions do.
        """
        leaves = source_card in (prediction.leaves_battlefield or [])
        if observed["source_present"] and observed["source_left_bf"] != leaves:
            return False
        want_pt = (prediction.pt_sets or {}).get(source_card)
        if want_pt is not None:
            if observed["source_curr_pt"] is None:
                return False
            if tuple(observed["source_curr_pt"]) != tuple(want_pt):
                return False
        seat_of = {
            p: seat for seat, p in getattr(self, "players", {}).items()
        }
        for target, delta in (prediction.life_deltas or {}).items():
            if delta == 0:
                continue
            seat = seat_of.get(target)
            if seat is None:
                continue
            observed_delta = observed["life_deltas"].get(seat)
            if observed_delta is None:
                continue
            if (observed_delta < 0) != (delta < 0):
                return False
        return True

    def _with_target_intent(
        self,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        thunk: Any,
    ) -> Any:
        """Run *thunk* with a replay-derived targeting Intent active.

        Queries raised while the thunk runs (ability targets, resolution
        choices) are answered by the acting seat's PlayerSubmittedTargets,
        falling back to the permissive baseline when the replay recorded
        none.
        """
        player = self.players.get(action.player_seat_id)
        if player is None or not hasattr(player, "start_intent"):
            return thunk()
        preferences = self._derive_target_preferences(
            action.player_seat_id, prev_snapshot, curr_snapshot,
            spell_iid=action.instance_id,
        )
        if not preferences:
            return thunk()
        from engine.decisions import GameRef
        from engine.intent_player import Intent

        intent_name = f"replay_ability_{action.instance_id}"
        player.start_intent(intent_name, Intent(
            pattern=GameRef(), preferences=preferences,
        ))
        try:
            return thunk()
        finally:
            player.end_intent(intent_name)

    def _resync_to_snapshot(
        self, snapshot: GameSnapshot, result: StepResult | None = None
    ) -> bool:
        """Oracle-correct engine state to the GRE snapshot (post-comparison).

        Corrects everything compare_state() checks — zone contents, life
        totals, tapped state, and P/T (via revocable oracle correction
        effects; printed and modified stats are never written directly) —
        so a divergence is reported exactly once and later steps validate
        independently.

        Returns True when GRE truth was fully restored, False when a card-code
        surface left a compared value uncorrected (only the P/T re-derivation's
        apply_all can — zone/life/tapped are pure, and trigger registration is
        guarded so it never aborts the zone sync). The executor's ``_synced``
        flag mirrors the return value: it is set False on entry and True only
        on full completion, so any early exit (a propagating protocol
        exception) leaves the executor marked dirty for the recovery barrier.
        Non-protocol card failures are recorded on ``result``; protocol
        exceptions propagate for classification.

        This method owns the compared-surface / P/T domain ALONE. It never
        reads or writes ``_operational_dirty``: operational untap state
        (summoning sickness, land plays) is not a surface compare_state checks,
        so restoring P/T says nothing about it. A successful resync therefore
        cannot promote an operationally-dirty executor to fully synchronized —
        the recovery barrier gates on both domains via ``_fully_synced``.
        """
        # Assume dirty until every compared surface is restored. (Only the
        # compared/P/T domain — the operational domain is untouched here.)
        self._synced = False

        # GRE's stack is empty but the engine still queues stack objects:
        # resolve them now (late) — Arena auto-resolves triggers without
        # distinct stack steps, so pending effects must land before sync.
        if self.game is not None:
            self._flush_pending_stack(snapshot)

        self._sync_zones(snapshot, result)

        for seat_id, snap_player in snapshot.players.items():
            player = self.players.get(seat_id)
            if player is not None and player.life != snap_player.life_total:
                player.life = snap_player.life_total

        for obj in snapshot.get_zone_objects("ZoneType_Battlefield"):
            card = self._engine_cards.get(obj.instance_id)
            if card is None:
                continue
            # Unconditional set: generic CardImpl shells don't define
            # is_tapped, and a hasattr guard would leave them diverged forever.
            card.is_tapped = obj.is_tapped

        pt_restored = self._rederive_pt_corrections(snapshot, result)
        self._synced = pt_restored
        return pt_restored

    def _flush_pending_stack(self, snapshot: GameSnapshot) -> None:
        """Resolve engine stack objects GRE has already auto-resolved.

        Whatever a late resolution fails to do is reconciled by the zone/life/
        tapped sync that follows (which overwrites those surfaces to GRE
        truth), so a non-protocol crash here is non-fatal and does not mark
        the executor dirty. Protocol exceptions propagate for classification.
        """
        gre_stack_empty = not any(
            zone.object_instance_ids
            for zone in snapshot.zones.values()
            if zone.type == "ZoneType_Stack"
        )
        if not gre_stack_empty:
            return
        guard = 0
        while not self.game.stack.is_empty() and guard < 50:
            guard += 1
            stack_obj = self.game.stack.pop()
            try:
                stack_obj.on_resolve(self.game)
            except Exception as exc:
                if _is_protocol_exception(exc):
                    raise
                logger.debug("late stack resolution failed", exc_info=True)

    # ------------------------------------------------------------------
    # Oracle P/T corrections (simulate-mode resync)
    # ------------------------------------------------------------------

    def _oracle_pt_corrections(self) -> list[Any]:
        """The currently registered replay-owned P/T correction effects."""
        if self.game is None:
            return []
        effect_manager = getattr(self.game, "effect_manager", None)
        if effect_manager is None:
            return []
        return effect_manager.get_effects_by_source(_ORACLE_PT_SOURCE)

    def _rederive_pt_corrections(
        self, snapshot: GameSnapshot, result: StepResult | None = None
    ) -> bool:
        """Clear-all-then-re-derive the oracle P/T corrections.

        A GRE-side P/T value the engine didn't reach is corrected with a
        revocable ContinuousEffect at Layer 7 / sublayer 7c, tagged with
        ``_ORACLE_PT_SOURCE``. Printed and modified stats are never written
        here — values move only through EffectManager's reset-then-apply
        discipline, so a temporary GRE-side effect can never leave
        permanent residue (the old base-stat bake oscillated forever).

        Every resync removes ALL prior corrections and re-derives from the
        residual delta per battlefield creature (never incremental), which
        also drops corrections whose object left the battlefield and gives
        fresh corrections the newest timestamps, so ``apply_all`` applies
        them after every real card effect. ``apply_all`` is triggered only
        when corrections are actually in play: undoing prior corrections
        needs one reset-then-apply pass, and newly registered corrections
        need one so this step's subsequent state (and the next step's
        comparison) sees corrected values — apply_all otherwise runs only
        at turn boundaries. The no-correction fast path never resets, so
        in-turn state that isn't effect-registered (direct stat mutations,
        counters not mirrored to ``_base_*``) is left untouched on the
        vast majority of steps.

        Returns True when the P/T surface was fully re-derived, False when the
        effect layer (``apply_all``) has crashed and correction is impossible
        — that is the only resync surface that leaves a compared value dirty.
        """
        if self.game is None:
            return True
        effect_manager = getattr(self.game, "effect_manager", None)
        if effect_manager is None:
            return True
        if self._effects_broken:
            # The effect layer already crashed this game; apply_all would only
            # re-crash. Skip it entirely — P/T stays uncorrected, so this
            # surface is dirty and the transition is unmeasurable. Reporting
            # False (rather than re-running the failing path) is what keeps
            # the recovery barrier from re-triggering the crash indefinitely.
            return False
        from engine.continuous_effects import (
            DURATION_PERMANENT,
            ContinuousEffect,
            Layer,
            SubLayer,
        )

        prior = effect_manager.get_effects_by_source(_ORACLE_PT_SOURCE)
        for effect in prior:
            effect_manager.remove(effect)
        canonical = False
        if prior:
            if not self._safe_apply_all(result):
                return False
            canonical = True

        # A permanent whose GRE counter is still deferred (its ETB object could
        # not be correlated yet) must NOT get a P/T correction here: the counter
        # lands next snapshot and would then double-count against a correction
        # installed for its absence. Skip such objects; the counter itself will
        # bridge the gap once it lands. Both the original and the churn-re-keyed
        # aid are skipped (the snapshot may already show the renamed id).
        pending_aids = {aid for (_ann, aid) in self._pending_counter_effects}
        pending_aids |= {
            p["current_aid"]
            for p in self._pending_counter_effects.values()
            if p.get("current_aid")
        }

        def residual_deltas() -> list[tuple[Any, int, int]]:
            deltas: list[tuple[Any, int, int]] = []
            for obj in snapshot.get_zone_objects("ZoneType_Battlefield"):
                if obj.instance_id in pending_aids:
                    continue
                card = self._engine_cards.get(obj.instance_id)
                if (
                    card is None
                    or not hasattr(card, "modified_power")
                    or not hasattr(card, "modified_toughness")
                ):
                    continue
                delta_p = obj.power - card.power if obj.power is not None else 0
                delta_t = (
                    obj.toughness - card.toughness
                    if obj.toughness is not None else 0
                )
                if delta_p or delta_t:
                    deltas.append((card, delta_p, delta_t))
            return deltas

        deltas = residual_deltas()
        if not deltas:
            return True
        if not canonical:
            # Corrections stack onto the reset-then-apply state, so the
            # residuals must be measured against it, not against live
            # state that may carry unregistered in-turn mutations.
            if not self._safe_apply_all(result):
                return False
            deltas = residual_deltas()
        for card, delta_p, delta_t in deltas:
            effect_manager.add(ContinuousEffect(
                source=_ORACLE_PT_SOURCE,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                duration=DURATION_PERMANENT,
                apply=self._make_pt_correction(card, delta_p, delta_t),
            ))
        if deltas:
            if not self._safe_apply_all(result):
                return False
        return True

    def _safe_apply_all(self, result: StepResult | None = None) -> bool:
        """Run ``effect_manager.apply_all``, guarding non-protocol card crashes.

        A card effect whose ``apply`` raises breaks the whole effect layer:
        apply_all applies nothing past the failure, so every later apply_all
        (here and in turn-boundary cleanup) would re-crash. Latch
        ``_effects_broken`` on the first such crash so those paths skip it,
        record an ENGINE_ERROR, and report failure. Protocol exceptions
        propagate for classification.
        """
        try:
            self.game.effect_manager.apply_all(self.game)
            return True
        except Exception as exc:
            if _is_protocol_exception(exc):
                raise
            self._effects_broken = True
            self._record_engine_failure(
                result,
                f"effect reapplication (apply_all): {type(exc).__name__}: {exc}",
            )
            return False

    def _record_engine_failure(
        self, result: StepResult | None, message: str
    ) -> None:
        """Record a non-protocol card failure as an ENGINE_ERROR, or log it.

        When a StepResult is in scope the failure becomes a per-action
        ENGINE_ERROR divergence; otherwise (e.g. a resync driven from the
        validation exception path) it is logged, matching the prior behavior
        of those call sites.
        """
        if result is not None:
            result.engine_failures.append(message)
        else:
            logger.debug(message, exc_info=True)

    def _make_pt_correction(self, card: Any, delta_p: int, delta_t: int) -> Any:
        """Build the apply callable for one oracle P/T correction."""
        def _apply(game: Any) -> None:
            # Battlefield-only: a correction outliving its object (cleared
            # at the next resync anyway) must not mutate off-battlefield
            # cards, whose stats apply_all's reset never restores.
            for player in game.players:
                if game.get_battlefield(player).contains(card):
                    card.modified_power += delta_p
                    card.modified_toughness += delta_t
                    return
        return _apply

    def execute_all(self) -> list[StepResult]:
        """Execute all snapshot transitions in the replay.

        Returns:
            List of StepResult objects, one per transition.
        """
        if not self._initialized:
            if self.replay.snapshots:
                self.initialize(self.replay.snapshots[0])
            else:
                return []

        results = []
        for i in range(1, len(self.replay.snapshots)):
            prev = self.replay.snapshots[i - 1]
            curr = self.replay.snapshots[i]
            result = self.execute_step(prev, curr)
            results.append(result)
            self.results.extend([result])

        return results

    # ------------------------------------------------------------------
    # State comparison
    # ------------------------------------------------------------------

    def compare_state(self, snapshot: GameSnapshot) -> list[StateMismatch]:
        """Compare engine state against a GRE snapshot.

        Checks:
        - Life totals
        - Zone contents (by grpId)
        - Battlefield permanents (tapped state, power/toughness)
        - Graveyard contents
        """
        mismatches: list[StateMismatch] = []

        # Life totals
        mismatches.extend(self._compare_life_totals(snapshot))

        # Zone contents
        mismatches.extend(self._compare_zones(snapshot))

        # Battlefield state (tapped, P/T) — only meaningful when the engine
        # actually plays the game (simulate mode). In observer mode the
        # engine never taps or modifies permanents, so comparing would just
        # flood the report with self-inflicted mismatches.
        if self.simulate:
            mismatches.extend(self._compare_battlefield(snapshot))

        return mismatches

    def _compare_life_totals(self, snapshot: GameSnapshot) -> list[StateMismatch]:
        """Compare life totals between engine and snapshot."""
        mismatches = []
        for seat_id, snap_player in snapshot.players.items():
            engine_player = self.players.get(seat_id)
            if engine_player is None:
                continue
            if engine_player.life != snap_player.life_total:
                mismatches.append(StateMismatch(
                    category="life_total",
                    description=f"Player {seat_id} life mismatch",
                    engine_value=engine_player.life,
                    snapshot_value=snap_player.life_total,
                    seat_id=seat_id,
                ))
        return mismatches

    def _compare_zones(self, snapshot: GameSnapshot) -> list[StateMismatch]:
        """Compare zone contents by grpId."""
        mismatches = []

        for engine_zone_enum, seat_id, zone_type_str, objs, expected_count in self._snapshot_zone_groups(snapshot):
            # Library: hidden identities, ordering differs.
            # Stack: transient and game-level in the engine.
            if zone_type_str in ("ZoneType_Library", "ZoneType_Stack"):
                continue
            # Opponent hand is hidden — contents unknowable.
            if seat_id != self.replay.seat_id and zone_type_str == "ZoneType_Hand":
                continue

            player = self.players.get(seat_id)
            if player is None:
                continue

            snap_grp_ids = sorted(obj.grp_id for obj in objs)

            engine_cards = player.zones[engine_zone_enum].get_all()
            engine_grp_ids = sorted(
                self._card_to_grp_id(card)
                for card in engine_cards
            )

            if snap_grp_ids != engine_grp_ids:
                mismatches.append(StateMismatch(
                    category="zone_contents",
                    description=f"Zone {zone_type_str} (seat {seat_id}) content mismatch",
                    engine_value=engine_grp_ids,
                    snapshot_value=snap_grp_ids,
                    seat_id=seat_id,
                ))

        return mismatches

    def _compare_battlefield(self, snapshot: GameSnapshot) -> list[StateMismatch]:
        """Compare battlefield state (tapped, P/T)."""
        mismatches = []

        bf_objects = snapshot.get_zone_objects("ZoneType_Battlefield")
        for obj in bf_objects:
            engine_card = self._engine_cards.get(obj.instance_id)
            if engine_card is None:
                continue

            # Tapped state
            engine_tapped = getattr(engine_card, "is_tapped", False)
            if engine_tapped != obj.is_tapped:
                mismatches.append(StateMismatch(
                    category="tapped_state",
                    description=f"{getattr(engine_card, 'name', '?')} tapped state mismatch",
                    engine_value=engine_tapped,
                    snapshot_value=obj.is_tapped,
                    seat_id=obj.owner_seat_id,
                ))

            # Power/toughness for creatures
            if obj.power is not None and hasattr(engine_card, "power"):
                if engine_card.power != obj.power:
                    mismatches.append(StateMismatch(
                        category="power_toughness",
                        description=f"{getattr(engine_card, 'name', '?')} power mismatch",
                        engine_value=engine_card.power,
                        snapshot_value=obj.power,
                        seat_id=obj.owner_seat_id,
                    ))

            if obj.toughness is not None and hasattr(engine_card, "toughness"):
                if engine_card.toughness != obj.toughness:
                    mismatches.append(StateMismatch(
                        category="power_toughness",
                        description=f"{getattr(engine_card, 'name', '?')} toughness mismatch",
                        engine_value=engine_card.toughness,
                        snapshot_value=obj.toughness,
                        seat_id=obj.owner_seat_id,
                    ))

        return mismatches

    # ------------------------------------------------------------------
    # Seat 1 (17lands user): Full validation
    # ------------------------------------------------------------------

    def _execute_seat1_action(
        self,
        action: ReplayAction,
        prev: GameSnapshot,
        curr: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Execute a Seat 1 action through the engine API."""
        if action.action_type == "land_play":
            self._execute_land_play(action, result)
        elif action.action_type == "spell_cast":
            self._execute_spell_cast(action, result)
        elif action.action_type == "draw":
            self._execute_draw(action, result)
        elif action.action_type == "creature_death":
            self._execute_creature_death(action, result)
        elif action.action_type in ("ability_activation", "ability_resolution"):
            self._execute_ability_resolution(action, prev, curr, result)
        else:
            # Unknown action — skip with note
            result.skipped = True
            result.skip_reason = f"unsupported action type: {action.action_type}"

    def _execute_land_play(self, action: ReplayAction, result: StepResult) -> None:
        """Execute a land play through the engine API (play_land)."""
        from engine.types import Zone

        player = self.players.get(action.player_seat_id)
        if player is None or self.game is None:
            result.success = False
            return

        # Find the land in hand
        hand = player.zones[Zone.HAND]
        card = self._find_card_by_grp_id(hand.get_all(), action.grp_id)
        if card is None:
            card = self._find_card_by_name(hand.get_all(), action.card_name)

        if card is None:
            if self.simulate:
                # Materialize from a hidden-hand shell (opponent lands,
                # alt-printing basics) so the play still runs through the engine.
                curr = self._current_snapshot
                if curr is not None:
                    card = self._take_from_hand(player, action, curr)
            if card is None:
                result.skipped = True
                result.skip_reason = f"land {action.card_name} not found in hand"
                return

        # Try engine API first
        try:
            from engine.casting import play_land
            play_land(self.game, player, card)
        except Exception as exc:
            # ENGINE LIMITATION: oracle-injected — engine timing/phase checks
            # may not match replay state; fall back to direct zone mutation.
            if self.simulate:
                result.engine_failures.append(
                    f"play_land {action.card_name}: {type(exc).__name__}: {exc}"
                )
            logger.debug(f"play_land engine API failed ({exc}), falling back to direct move")
            if hand.contains(card):
                hand.remove(card)
            battlefield = player.zones[Zone.BATTLEFIELD]
            if not battlefield.contains(card):
                battlefield.add(card)

        # Update instance map
        if action.instance_id:
            self._engine_cards[action.instance_id] = card

        logger.debug(f"Seat 1 played land: {action.card_name}")

    def _execute_spell_cast(self, action: ReplayAction, result: StepResult) -> None:
        """Execute a spell cast through the engine.

        For permanents: hand → battlefield (stack resolution skipped).
        For instants/sorceries: hand → graveyard (stack resolution skipped).
        # ENGINE LIMITATION: oracle-injected — full stack simulation not yet
        # integrated; we model the correct final destination but skip the
        # hand → stack → resolve pipeline.
        """
        from engine.types import CardType, Zone

        player = self.players.get(action.player_seat_id)
        if player is None or self.game is None:
            result.success = False
            return

        hand = player.zones[Zone.HAND]
        card = self._find_card_by_grp_id(hand.get_all(), action.grp_id)
        if card is None:
            card = self._find_card_by_name(hand.get_all(), action.card_name)

        if card is None:
            result.skipped = True
            result.skip_reason = f"spell {action.card_name} not found in hand"
            return

        # Determine destination based on card type
        card_types = getattr(card, "card_types", set())
        is_instant_or_sorcery = bool(
            card_types & {CardType.INSTANT, CardType.SORCERY}
        )

        hand.remove(card)
        if is_instant_or_sorcery:
            # Instants/sorceries resolve to graveyard
            graveyard = player.zones[Zone.GRAVEYARD]
            graveyard.add(card)
        else:
            # Permanents resolve to battlefield
            battlefield = player.zones[Zone.BATTLEFIELD]
            battlefield.add(card)

        if action.instance_id:
            self._engine_cards[action.instance_id] = card

        logger.debug(f"Seat 1 cast spell: {action.card_name}")

    def _execute_draw(self, action: ReplayAction, result: StepResult) -> None:
        """Execute a card draw through the engine."""
        from engine.game import draw_card

        player = self.players.get(action.player_seat_id)
        if player is None or self.game is None:
            result.success = False
            return

        drawn = draw_card(self.game, player)
        if drawn is not None:
            # Tag drawn card with grpId for tracking
            drawn._grp_id = action.grp_id
            if action.instance_id:
                self._engine_cards[action.instance_id] = drawn

        logger.debug(f"Seat 1 drew card: {action.card_name}")

    def _execute_creature_death(self, action: ReplayAction, result: StepResult) -> None:
        """Handle creature death for seat 1 using engine move_to_zone."""
        from engine.types import Zone

        player = self.players.get(action.player_seat_id)
        if player is None or self.game is None:
            result.success = False
            return

        bf = player.zones[Zone.BATTLEFIELD]
        card = self._find_card_by_grp_id(bf.get_all(), action.grp_id)
        if card is None:
            card = self._find_card_by_name(bf.get_all(), action.card_name)

        if card is None:
            result.skipped = True
            result.skip_reason = f"creature {action.card_name} not on battlefield"
            return

        # Use engine move_to_zone for proper trigger/replacement handling
        try:
            from engine.events import CreatureDiesReplacementEvent
            from engine.zones import move_to_zone
            move_to_zone(
                self.game, card, Zone.BATTLEFIELD, Zone.GRAVEYARD,
                replacement_event=CreatureDiesReplacementEvent(
                    creature=card,
                    controller=getattr(card, "controller", player),
                    owner=getattr(card, "owner", player),
                ),
            )
        except Exception as exc:
            # ENGINE LIMITATION: oracle-injected — move_to_zone may fail
            # if card state is inconsistent; fall back to direct mutation.
            if self.simulate:
                result.engine_failures.append(
                    f"move_to_zone (creature_death) {action.card_name}: "
                    f"{type(exc).__name__}: {exc}"
                )
            logger.debug(f"move_to_zone failed ({exc}), falling back to direct move")
            if bf.contains(card):
                bf.remove(card)
            gy = player.zones[Zone.GRAVEYARD]
            if not gy.contains(card):
                gy.add(card)

        if action.instance_id:
            self._engine_cards[action.instance_id] = card

    # ------------------------------------------------------------------
    # Seat 2 (opponent): Oracle injection
    # ------------------------------------------------------------------

    def _inject_seat2_action(
        self,
        action: ReplayAction,
        prev: GameSnapshot,
        curr: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Inject a Seat 2 action directly into engine state without legality checks."""
        from engine.types import Zone

        player = self.players.get(action.player_seat_id)
        if player is None:
            result.skipped = True
            result.skip_reason = "opponent player not found"
            return

        if action.action_type == "land_play":
            card = self._create_card(action.grp_id, player)
            # Remove from hand if possible
            hand = player.zones[Zone.HAND]
            hand_card = self._find_card_by_grp_id(hand.get_all(), action.grp_id)
            if hand_card is not None:
                hand.remove(hand_card)
                card = hand_card
            player.zones[Zone.BATTLEFIELD].add(card)

            if action.instance_id:
                self._engine_cards[action.instance_id] = card

        elif action.action_type == "spell_cast":
            card = self._create_card(action.grp_id, player)
            hand = player.zones[Zone.HAND]
            hand_card = self._find_card_by_grp_id(hand.get_all(), action.grp_id)
            if hand_card is not None:
                hand.remove(hand_card)
                card = hand_card
            # Determine final destination based on card type
            from engine.types import CardType
            card_types = getattr(card, "card_types", set())
            is_instant_or_sorcery = bool(
                card_types & {CardType.INSTANT, CardType.SORCERY}
            )
            if is_instant_or_sorcery:
                player.zones[Zone.GRAVEYARD].add(card)
            else:
                player.zones[Zone.BATTLEFIELD].add(card)

            if action.instance_id:
                self._engine_cards[action.instance_id] = card

        elif action.action_type == "draw":
            # Opponent draws — move from library to hand if possible
            library = player.zones[Zone.LIBRARY]
            lib_card = self._find_card_by_grp_id(library.get_all(), action.grp_id)
            if lib_card is not None:
                library.remove(lib_card)
                card = lib_card
            else:
                card = self._create_card(action.grp_id, player)
            player.zones[Zone.HAND].add(card)

            if action.instance_id:
                self._engine_cards[action.instance_id] = card

        elif action.action_type == "creature_death":
            bf = player.zones[Zone.BATTLEFIELD]
            card = self._find_card_by_grp_id(bf.get_all(), action.grp_id)
            if card is not None:
                bf.remove(card)
                player.zones[Zone.GRAVEYARD].add(card)
                if action.instance_id:
                    self._engine_cards[action.instance_id] = card

        elif action.action_type in ("ability_activation", "ability_resolution"):
            self._execute_ability_resolution(action, prev, curr, result)

        else:
            result.skipped = True
            result.skip_reason = f"unsupported opponent action: {action.action_type}"

        logger.debug(f"Seat 2 oracle inject: {action.action_type} {action.card_name}")

    # ------------------------------------------------------------------
    # Ability resolution
    # ------------------------------------------------------------------

    def _find_ability_source(self, action: ReplayAction) -> Any | None:
        """Return the engine card that is the source of an ability action."""
        from engine.types import Zone

        parent_id = action.details.get("parent_id")
        if parent_id:
            card = self._engine_cards.get(parent_id)
            if card is not None:
                return card

        if action.grp_id:
            # Search the controller's battlefield first, then all players;
            # then graveyards — some abilities activate from there
            # (e.g. Reassembling Skeleton).
            seats = []
            if action.player_seat_id:
                seats.append(action.player_seat_id)
            seats.extend(s for s in self.players if s != action.player_seat_id)
            for zone in (Zone.BATTLEFIELD, Zone.GRAVEYARD):
                for seat_id in seats:
                    player = self.players.get(seat_id)
                    if player is None:
                        continue
                    card = self._find_card_by_grp_id(
                        player.zones[zone].get_all(), action.grp_id
                    )
                    if card is not None:
                        return card
        return None

    def _try_engine_ability_resolution(self, source_card: Any, card_name: str) -> bool:
        """Attempt to resolve an ability through the engine (registered cards only).

        Calls register_triggers on the source card, guarded against double-apply.
        Returns True if resolution succeeded, False if the fallback should be used.
        """
        if source_card is None or self.game is None:
            return False
        if not (self.registry is not None and card_name and card_name in self.registry):
            return False

        card_key = id(source_card)
        if card_key in self._triggers_registered:
            return True  # already applied for this card object

        try:
            source_card.register_triggers(self.game)
            self._triggers_registered.add(card_key)
            logger.debug("Ability engine resolved via register_triggers: %s", card_name)
            return True
        except Exception as exc:
            logger.warning(
                "Ability engine resolution failed for %s: %s — using snapshot fallback",
                card_name, exc,
            )
            return False

    def _apply_ability_life_fallback(
        self,
        card_name: str,
        curr: GameSnapshot,
    ) -> None:
        """Apply any remaining life delta to close the gap to the snapshot value.

        Called when engine resolution fails or the card is unregistered.
        Only adjusts life that hasn't already been updated by the engine, so
        multiple fallback calls in the same snapshot are idempotent.
        """
        for seat_id, curr_player_info in curr.players.items():
            engine_player = self.players.get(seat_id)
            if engine_player is None:
                continue
            delta = curr_player_info.life_total - engine_player.life
            if delta == 0:
                continue
            engine_player.life += delta
            logger.warning(
                "Ability fallback: %s — applied life delta %+d to player %d "
                "(engine resolution failed or card unregistered)",
                card_name, delta, seat_id,
            )

    def _execute_ability_resolution(
        self,
        action: ReplayAction,
        prev: GameSnapshot,
        curr: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Handle an ability_activation or ability_resolution action.

        For ability_activation: no-op if the ability is still on the stack
        (effects will be applied when ability_resolution fires). Acts
        immediately only if the ability already left the stack in the
        same snapshot transition (auto-resolved triggers are rare in practice
        but handled here as a guard).

        For ability_resolution: always attempt engine resolution first
        (register_triggers on registered cards), then fall back to a
        snapshot life-delta sync if the engine can't handle it.
        Zone-level effects (tokens, moved cards) are handled by _sync_zones
        which runs after this method.
        """
        if action.action_type == "ability_activation":
            if action.instance_id in curr.game_objects:
                return  # ability still on stack; handle at resolution time

        card_name = (
            action.card_name
            or self._grp_to_name.get(action.grp_id, f"grpId={action.grp_id}")
        )
        source_card = self._find_ability_source(action)

        if not self._try_engine_ability_resolution(source_card, card_name):
            self._apply_ability_life_fallback(card_name, curr)

    def _reconcile_life_totals(self, prev: GameSnapshot, curr: GameSnapshot) -> None:
        """Apply any life total deltas not handled by the action itself.

        The engine doesn't model all sources of life change (combat damage,
        lifelink, unregistered abilities, etc.). After each action handler runs,
        this method checks whether the snapshot shows a life total the engine
        didn't reach, and corrects it.

        Each correction is logged at info level — these are engine gaps worth
        tracking for future improvement.
        """
        for seat_id in curr.players:
            prev_player = prev.players.get(seat_id)
            curr_player = curr.players.get(seat_id)
            if prev_player is None or curr_player is None:
                continue
            expected_life = curr_player.life_total
            engine_player = self.players.get(seat_id)
            if engine_player is None:
                continue
            if engine_player.life != expected_life:
                delta = expected_life - engine_player.life
                engine_player.life = expected_life
                logger.info(
                    "Life reconciliation: player %d %+d (engine had %d, snapshot says %d)",
                    seat_id, delta, expected_life - delta, expected_life,
                )

    # ------------------------------------------------------------------
    # Token correlation (engine-minted token ↔ GRE token identity)
    # ------------------------------------------------------------------

    def _engine_token_signature(self, card: Any) -> tuple:
        """Correlation signature for an engine token (see _token_signature)."""
        card_types = [
            getattr(t, "value", t) for t in getattr(card, "card_types", []) or []
        ]
        return _token_signature(
            card_types,
            getattr(card, "subtypes", None),
            getattr(card, "base_power", None),
            getattr(card, "base_toughness", None),
        )

    def _engine_token_color_key(self, card: Any) -> frozenset | None:
        """Normalized colour of an engine token, or ``None`` when it is UNKNOWN.

        Distinguishes two states the old empty-frozenset representation
        conflated, because they carry OPPOSITE evidential weight in a colliding
        signature:

        - **Known colour** — the token establishes a colour through an
          authoritative source: an explicit ``colors`` attribute (the token-impl
          idiom ``token.colors = {Color.WHITE}``), coloured mana pips, or an
          explicit ``color``. An explicit but EMPTY ``colors`` set (or a mana
          cost of only generic pips) is *positive colourless evidence* under a
          documented rule and returns the empty frozenset.
        - **Unknown colour** — none of those sources is present, so the token
          never established a colour. Returns ``None``. Unknown is NOT
          colourless: an undeclared token must not be matched to a colourless
          candidate by colour equality the way an explicitly-colourless one is;
          the honest outcome is to leave it unstamped unless other reliable
          evidence (a copy-card name) resolves it.

        Source precedence mirrors ``engine.protection.get_colors`` so a token
        that IS coloured reads identically; this only adds the
        unknown/colourless split get_colors cannot express (it flattens both to
        an empty set).
        """
        colors = getattr(card, "colors", None)
        mana_cost = getattr(card, "mana_cost", None)
        has_pips = mana_cost is not None and bool(getattr(mana_cost, "pips", None))
        single_color = getattr(card, "color", None)
        # No authoritative colour source at all → UNKNOWN, not colourless.
        if colors is None and not has_pips and single_color is None:
            return None
        try:
            from engine.protection import get_colors

            return _color_key(get_colors(card))
        except Exception:
            if colors is not None:
                return _color_key(colors)
            if single_color is not None:
                return _color_key([single_color])
            return frozenset()

    def _correlate_tokens_in_group(
        self, gre_objs: list[Any], engine_cards: list[Any]
    ) -> None:
        """Stamp id-less engine tokens with their GRE grpId, matched by identity.

        Matches id-less engine battlefield tokens to the GRE token objects
        present in the same group, keyed on the token identity map: a match
        needs the same characteristic signature (card types, subtypes, and —
        for creatures — base P/T, which is what tells the two red Dragon tokens
        apart). Only grpIds the map recognizes are ever stamped.

        Identity-safety rule (KEY_DECISIONS): a stamp is made ONLY when the
        available evidence identifies the grpId uniquely. Ambiguity is decided
        MAP-WIDE (``TokenIdMap.signature_candidates``), never from the identities
        this snapshot happens to show — a signature two grpIds share is ambiguous
        even in a group that contains only one of them.

        - A GLOBALLY-UNIQUE signature (only one map identity can carry it) → an
          unambiguous match. Duplicates of that single identity are
          interchangeable (rule 601) and are matched by COUNT, never guessed
          order.
        - A GLOBALLY-COLLIDING signature (several DISTINCT map grpIds share it,
          e.g. the 1/1 red Human copy 93797 and the 1/1 white Human 94158) → the
          engine object is NEVER distributed among the candidates by grpId or
          zone order, NOR inferred from being the only colliding identity the
          snapshot shows. Each object is validated against the COMPLETE collision
          set on real evidence — its known colour narrows the set and, for a copy
          candidate, a matching copy-card name is REQUIRED, so every discriminator
          must agree; output is restricted to the identities GRE actually contains
          here. An object whose evidence does not pick out exactly one GRE-present
          identity — a contradictory colour, a copy name that contradicts the
          colour-unique candidate, an unknown colour, or nothing that separates
          two same-colour Rats (93883 vs 94169) — is left id-less so comparison
          and resync record the gap.

        An ambiguous grpId is never added to ``_minted_token_grpids``. An engine
        token the map can't match stays id-0 and is handled exactly as before
        (the overflow pass may remove it). Idempotent: already-stamped tokens are
        skipped, so calling it twice a step is safe.
        """
        if self.token_map is None:
            return

        # GRE tokens present whose grpId the map recognizes, bucketed by
        # signature; a signature may cover more than one distinct grpId. The
        # per-grpId GRE instance ids are collected so a stamped engine token can
        # be bound to a distinct stint id for counter sync.
        gre_by_sig: dict[tuple, Counter] = {}
        gre_aids_by_grp: dict[int, list[int]] = {}
        for obj in gre_objs:
            if obj.type != "GameObjectType_Token":
                continue
            if not self.token_map.is_token(obj.grp_id):
                continue
            sig = self.token_map.signature(obj.grp_id)
            if sig is None:
                continue
            gre_by_sig.setdefault(sig, Counter())[obj.grp_id] += 1
            gre_aids_by_grp.setdefault(obj.grp_id, []).append(obj.instance_id)
        if not gre_by_sig:
            return

        # Id-less engine tokens bucketed by the same signature.
        idless: dict[tuple, list[Any]] = {}
        for card in engine_cards:
            if not getattr(card, "is_token", False):
                continue
            if getattr(card, "_grp_id", None):
                continue
            idless.setdefault(self._engine_token_signature(card), []).append(card)

        for sig, grp_counter in gre_by_sig.items():
            pool = idless.get(sig)
            if not pool:
                continue
            candidates = self.token_map.signature_candidates(sig)
            if len(candidates) <= 1:
                # Globally unique signature: only one identity can ever carry it,
                # so present duplicates are interchangeable and matched by count.
                (grp_id,) = grp_counter
                self._stamp_tokens(
                    pool, grp_id, grp_counter[grp_id], gre_aids_by_grp.get(grp_id)
                )
            else:
                # Globally colliding signature: several distinct identities share
                # it map-wide. Validate each engine object against the COMPLETE
                # collision set and restrict output to the GRE-present identities
                # — presence of a single candidate never proves an object's id.
                self._correlate_colliding_signature(
                    grp_counter, candidates, pool, gre_aids_by_grp
                )

    def _stamp_tokens(
        self,
        pool: list[Any],
        grp_id: int,
        count: int,
        aids: list[int] | None = None,
    ) -> None:
        """Stamp up to *count* still-id-less *pool* tokens with *grp_id*.

        Marks the identity producible in ``_minted_token_grpids`` only for the
        objects actually stamped. Skips any object already carrying a grpId so
        repeat calls within a step are idempotent. When *aids* is supplied, each
        stamped token is also bound to a distinct GRE instance id (in order) via
        ``_bind_counter_token`` so counter sync can reach a just-minted token
        that is not yet in ``_engine_cards``.
        """
        stamped = 0
        for card in pool:
            if stamped >= count:
                break
            if getattr(card, "_grp_id", None):
                continue
            card._grp_id = grp_id
            self._minted_token_grpids.add(grp_id)
            if aids is not None and stamped < len(aids):
                self._bind_counter_token(aids[stamped], card)
            stamped += 1

    def _bind_counter_token(self, aid: int, card: Any) -> None:
        """Publish a GRE-instance-id -> engine-token binding for counter sync."""
        self._counter_token_binding[aid] = card

    def _correlate_colliding_signature(
        self,
        present_counter: Counter,
        candidates: set[int],
        pool: list[Any],
        gre_aids_by_grp: dict[int, list[int]] | None = None,
    ) -> None:
        """Correlate engine tokens whose signature collides across the map.

        A colliding signature is one several distinct grpIds share MAP-WIDE, so
        signature + count can never prove identity — that would be inferring an
        object's identity from whichever colliding grpId the snapshot happens to
        show. Each engine object is instead validated against the COMPLETE
        collision set (*candidates*): every available discriminator — its known
        colour AND, for a copy candidate, a matching copy-card name — must AGREE
        and together pick out exactly one member (see
        ``_resolve_colliding_identity``). The result is then restricted to the
        identities GRE actually contains in this group (*present_counter*) and
        bounded by their counts.

        Contradictory evidence — a colour that resolves to a candidate GRE does
        not show here (e.g. a red engine Human when GRE shows only the white
        94158), a copy name that contradicts the only colour-consistent
        candidate (a red 1/1 Human named "Human", not the copy "Dragon
        Trainer"), or no candidate all evidence agrees on — and insufficient
        evidence — nothing uniquely separates the survivors (two same-colour
        Rats, or an unknown-colour token) — both leave the object id-less, so
        compare/resync exposes the uncertainty and the unproven identity is
        never marked producible.
        """
        # Only identities present in this group may be output; ``budget`` also
        # caps each at its GRE count. A Counter read for an absent identity is 0,
        # so a resolved-but-not-present identity is naturally rejected.
        budget = Counter(present_counter)
        # Per-grpId cursor into the GRE stint ids, so each resolved engine token
        # binds to a distinct instance id for counter sync.
        aid_cursor: dict[int, int] = {}
        for card in pool:
            if getattr(card, "_grp_id", None):
                continue
            grp_id = self._resolve_colliding_identity(card, candidates)
            if grp_id is None:
                continue  # contradictory or insufficient evidence → id-less
            if budget[grp_id] <= 0:
                # The engine object resolves to an identity GRE does not show
                # here (its evidence contradicts the snapshot) or that identity's
                # count is already exhausted. Either way: leave it id-less.
                continue
            card._grp_id = grp_id
            self._minted_token_grpids.add(grp_id)
            budget[grp_id] -= 1
            if gre_aids_by_grp is not None:
                aids = gre_aids_by_grp.get(grp_id, [])
                idx = aid_cursor.get(grp_id, 0)
                if idx < len(aids):
                    self._bind_counter_token(aids[idx], card)
                    aid_cursor[grp_id] = idx + 1

    def _resolve_colliding_identity(
        self, card: Any, candidates: set[int]
    ) -> int | None:
        """The one collision-set identity ALL of *card*'s evidence agrees on.

        Validated against the COMPLETE collision set, never narrowed to the
        snapshot first — so an engine object cannot borrow the identity of "the
        only colliding grpId GRE shows". Returns a grpId only when every
        available reliable discriminator is mutually consistent and together
        they pick out exactly ONE candidate; anything less → ``None``.

        Colour NARROWS the collision set but never resolves it alone. A KNOWN
        colour keeps only candidates whose recorded colour EQUALS it (a
        contradictory colour eliminates them). An UNKNOWN colour (undeclared —
        see ``_engine_token_color_key``) is the ABSENCE of evidence: it
        eliminates nothing AND selects nothing, so it can never pick a
        colourless candidate the way an explicitly-colourless token can.

        Every candidate that survives the colour narrowing is then checked for
        NAME consistency — so colour can never override a contradictory copy
        name:

        - A COPY candidate (its map entry records the copied card's ``name``)
          is established only if the engine object's name EQUALS that copied
          name: required, affirmative evidence. A present but different name
          contradicts the copy and eliminates it; a missing name cannot confirm
          it. (Red 1/1 Human ``Dragon Trainer`` → 93797; red 1/1 Human
          ``Human`` stays id-less.)
        - A GENERIC candidate (no recorded copy name) can never be established
          by name — a generic token's name is impl-dependent and is not positive
          evidence. It is established only when a KNOWN colour has already
          isolated it as the SOLE colour-consistent candidate, and never
          inferred by elimination once a same-colour copy is ruled out. (Black
          1/1 Rat ``Burglar Rat`` → 93883; black 1/1 Rat ``Rat`` stays id-less
          rather than inferring 94169.)

        Exactly one established candidate → its grpId; zero or several →
        ``None``.
        """
        engine_color = self._engine_token_color_key(card)
        engine_name = getattr(card, "name", None)

        if engine_color is not None:
            survivors = {
                grp_id for grp_id in candidates
                if self.token_map.color_key(grp_id) == engine_color
            }
        else:
            # Unknown colour eliminates nothing and (below) establishes no
            # generic — only a matching copy name can resolve such a token.
            survivors = set(candidates)

        established: set[int] = set()
        for grp_id in survivors:
            copy_name = self.token_map.token_name(grp_id)
            if copy_name is not None:
                # Copy candidate: the copied-card name is a required check.
                if engine_name is not None and engine_name == copy_name:
                    established.add(grp_id)
            elif engine_color is not None and len(survivors) == 1:
                # Generic candidate: only a KNOWN colour that uniquely isolates
                # it establishes it — never name, never elimination.
                established.add(grp_id)

        if len(established) == 1:
            (grp_id,) = established
            return grp_id
        return None

    def _correlate_tokens(self, snapshot: GameSnapshot) -> None:
        """Correlate engine-minted tokens across every battlefield group.

        Called before ``compare_state`` (so the comparison sees stamped tokens)
        and again inside ``_sync_zones`` (so tokens minted while the resync
        resolves the late stack are stamped before the overflow pass runs).

        The token->engine binding published for counter sync is rebuilt fresh
        each snapshot (a persistent token moves into ``_engine_cards`` after the
        first rebuild, so the binding is only needed the snapshot a token first
        appears; a stale cross-snapshot entry must never mislead resolution).
        """
        if not self.simulate or self.token_map is None:
            return
        self._counter_token_binding.clear()
        for engine_zone_enum, seat_id, zone_type_str, objs, _ in (
            self._snapshot_zone_groups(snapshot)
        ):
            if zone_type_str != "ZoneType_Battlefield":
                continue
            player = self.players.get(seat_id)
            if player is None:
                continue
            self._correlate_tokens_in_group(
                objs, player.zones[engine_zone_enum].get_all()
            )

    # ------------------------------------------------------------------
    # Zone sync (untracked card appearances)
    # ------------------------------------------------------------------

    def _sync_zones(
        self, snapshot: GameSnapshot, result: StepResult | None = None
    ) -> None:
        """Sync engine zones with snapshot for cards that appeared without
        tracked ObjectIdChanged annotations (opening hands, mulligans, etc.).

        Compares grpId multisets per zone. Injects missing cards into the
        engine and removes excess cards. Library and Stack are skipped.

        Runs card code only for oracle-injected battlefield permanents
        (``register_triggers``/``register_replacement_effects``), and that is
        guarded per card so a crash there never aborts the sync — the compared
        surfaces (contents, tapped, P/T) are fully reconciled regardless.
        """
        # Library: hidden and order-dependent, inferred via draw actions.
        # Stack: transient; engine models entries differently than GRE.
        SKIP_ZONES = {"ZoneType_Library", "ZoneType_Stack"}

        for engine_zone_enum, seat_id, zone_type_str, objs, expected_count in self._snapshot_zone_groups(snapshot):
            if zone_type_str in SKIP_ZONES:
                continue

            player = self.players.get(seat_id)
            if player is None:
                continue

            # Correlate engine-minted tokens to their GRE grpId BEFORE the
            # multiset comparison, so a matched token counts as its real grpId:
            # it is no longer shell-injected nor deleted by the overflow pass.
            # Simulate-only — observer mode is byte-for-byte unchanged.
            if self.simulate and zone_type_str == "ZoneType_Battlefield":
                self._correlate_tokens_in_group(
                    objs, player.zones[engine_zone_enum].get_all()
                )

            # grpId multiset from snapshot (skip unknown grpId=0)
            snap_grp_ids: Counter[int] = Counter(
                obj.grp_id for obj in objs if obj.grp_id != 0
            )
            sample_obj = {obj.grp_id: obj for obj in objs if obj.grp_id != 0}

            # grpId multiset via engine (skip grpId=0)
            engine_cards_list = player.zones[engine_zone_enum].get_all()
            engine_grp_ids: Counter[int] = Counter(
                gid for card in engine_cards_list
                if (gid := self._card_to_grp_id(card)) != 0
            )

            is_battlefield = zone_type_str == "ZoneType_Battlefield"

            # Inject cards present in snapshot but missing in engine
            for grp_id, snap_count in snap_grp_ids.items():
                deficit = snap_count - engine_grp_ids.get(grp_id, 0)
                for _ in range(deficit):
                    card = self._create_card_from_object(sample_obj[grp_id], player)
                    player.zones[engine_zone_enum].add(card)
                    if self.simulate and is_battlefield:
                        # Oracle-injected permanents still participate in the
                        # simulated game — register their triggers/effects.
                        self._register_injected_triggers(card, result)
                    logger.debug(
                        "_sync_zones: injected grpId=%d into %s (seat %d)",
                        grp_id, zone_type_str, seat_id,
                    )

            # Remove cards present in engine but absent from snapshot
            engine_cards_list = player.zones[engine_zone_enum].get_all()
            for grp_id, engine_count in engine_grp_ids.items():
                excess = engine_count - snap_grp_ids.get(grp_id, 0)
                if excess > 0:
                    to_remove = [
                        c for c in engine_cards_list
                        if self._card_to_grp_id(c) == grp_id
                    ]
                    for card in to_remove[:excess]:
                        self._remove_synced_card(player, engine_zone_enum, card, is_battlefield)
                        logger.debug(
                            "_sync_zones: removed grpId=%d from %s (seat %d)",
                            grp_id, zone_type_str, seat_id,
                        )

            # Engine-created objects without a grpId (tokens minted by
            # triggers/resolutions) can't be matched per-grpId; when the
            # engine zone holds more cards than the snapshot, they are the
            # excess — remove them or they diverge forever. The comparison
            # is against expected_count, NOT len(objs): hidden objects
            # (opponent hand) appear in the zone id-list without
            # game_objects entries, and their engine-side shells are
            # legitimate residents, not overflow.
            engine_cards_list = player.zones[engine_zone_enum].get_all()
            overflow = len(engine_cards_list) - expected_count
            if overflow > 0:
                grp0_cards = [
                    c for c in engine_cards_list if self._card_to_grp_id(c) == 0
                ]
                for card in grp0_cards[:overflow]:
                    self._remove_synced_card(player, engine_zone_enum, card, is_battlefield)
                    logger.debug(
                        "_sync_zones: removed unidentified engine card %r from %s (seat %d)",
                        getattr(card, "name", "?"), zone_type_str, seat_id,
                    )

        self._rebuild_instance_map(snapshot)

    def _register_injected_triggers(
        self, card: Any, result: StepResult | None = None
    ) -> None:
        """Register an oracle-injected permanent's triggers/replacement effects.

        Card code — a crash here (e.g. a card whose ``register_triggers`` hits
        a ``NameError``) is a per-card failure, never a sync abort: the
        permanent is already in its zone, so contents/tapped/P/T still
        reconcile; only that card's own triggers go unregistered. Recorded as
        an ENGINE_ERROR; protocol exceptions propagate for classification.
        """
        for method in ("register_triggers", "register_replacement_effects"):
            fn = getattr(card, method, None)
            if fn is None:
                continue
            try:
                fn(self.game)
            except Exception as exc:
                if _is_protocol_exception(exc):
                    raise
                self._record_engine_failure(
                    result,
                    f"{method} {getattr(card, 'name', '?')}: "
                    f"{type(exc).__name__}: {exc}",
                )

    def _remove_synced_card(
        self, player: Any, engine_zone: Any, card: Any, is_battlefield: bool
    ) -> None:
        """Remove a card during zone sync, with trigger cleanup on battlefield."""
        player.zones[engine_zone].remove(card)
        if self.simulate and is_battlefield and self.game is not None:
            # Symmetric cleanup — stale triggers and continuous effects
            # must not keep applying for a permanent GRE says is gone.
            self.game.trigger_manager.unregister(card)
            self.game.replacement_manager.unregister(card)
            effect_manager = getattr(self.game, "effect_manager", None)
            if effect_manager is not None:
                for effect in effect_manager.get_effects_by_source(card):
                    effect_manager.remove(effect)

    # ------------------------------------------------------------------
    # Turn info / phase handling
    # ------------------------------------------------------------------

    # GRE phase/step strings → engine Phase/Step enum value names.
    # (There is no Step_Untap in GRE streams — Arena untaps implicitly at
    # the turn boundary, so simulate mode untaps on turn-number change.)
    _GRE_PHASE_TO_ENGINE: dict[str, str] = {
        "Phase_Beginning": "beginning",
        "Phase_Main1": "precombat_main",
        "Phase_Combat": "combat",
        "Phase_Main2": "postcombat_main",
        "Phase_Ending": "ending",
    }
    _GRE_STEP_TO_ENGINE: dict[str, str] = {
        "Step_Upkeep": "upkeep",
        "Step_Draw": "draw",
        "Step_BeginCombat": "begin_combat",
        "Step_DeclareAttack": "declare_attackers",
        "Step_DeclareBlock": "declare_blockers",
        "Step_FirstStrikeDamage": "combat_damage",
        "Step_CombatDamage": "combat_damage",
        "Step_EndCombat": "end_combat",
        "Step_End": "end",
        "Step_Cleanup": "cleanup",
    }

    def _handle_turn_info(
        self,
        prev_turn: TurnInfo,
        curr_turn: TurnInfo,
        result: StepResult | None = None,
    ) -> None:
        """Handle phase/step transitions from turnInfo diffs."""
        if self.game is None:
            return

        turn_changed = (
            curr_turn.turn_number != prev_turn.turn_number
            and curr_turn.turn_number > 0
        )

        # Update turn number
        if turn_changed:
            self.game.turn_number = curr_turn.turn_number

        # Update active player
        if curr_turn.active_player != prev_turn.active_player and curr_turn.active_player > 0:
            seat = curr_turn.active_player
            # Map seat to player index
            for i, p_seat in enumerate(sorted(self.players.keys())):
                if p_seat == seat:
                    self.game.active_player_index = i
                    break

        if not self.simulate:
            return

        # --- Simulate mode: follow GRE turn structure through the engine ---
        from engine.types import Phase, Step

        if turn_changed:
            # New turn: cleanup for the ending turn (until-EOT effects
            # expire, marked damage clears, combat flags reset), then the
            # engine untap step for the (already updated) active player —
            # untap, clear summoning sickness, reset land plays. Arena has
            # no visible cleanup step; the turn boundary is its moment.
            #
            # Cleanup and untap are guarded INDEPENDENTLY: cleanup's effect
            # reapplication (apply_all) runs card code, but untap is pure
            # engine bookkeeping. A cleanup crash must not cost us the untap,
            # so a failure in one never skips the other. Protocol exceptions
            # propagate from both.
            from engine.turn import untap_step
            try:
                self._replay_cleanup()
            except Exception as exc:
                if _is_protocol_exception(exc):
                    raise
                self._record_engine_failure(
                    result,
                    f"turn-boundary cleanup: {type(exc).__name__}: {exc}",
                )
                # cleanup_mechanical crashes at its leading apply_all, before
                # the deterministic damage/flag/mana resets (rule 514 steps
                # 3-5) run. Those fields are not compared by compare_state, so
                # they need no direct restore — but the effect layer is now
                # broken (every later apply_all re-crashes), so latch it and
                # mark the executor dirty: the recovery barrier restores the
                # compared surfaces (zones, life, tapped, P/T) before the next
                # measured transition, or suppresses it as unmeasurable.
                self._effects_broken = True
                self._synced = False
            try:
                untap_step(self.game)
            except Exception as exc:
                if _is_protocol_exception(exc):
                    # A protocol exception surfaces per the engine's contract
                    # (PROTOCOL_ERROR / QUERY_UNANSWERED) and must NOT be
                    # converted to an ENGINE_ERROR — so nothing is recorded on
                    # result here. But a broken untap can partially mutate state
                    # and then raise a protocol exception too, and the validator
                    # that catches this re-raise resyncs only the compared / P/T
                    # surfaces (setting _synced True); it never touches the
                    # operational domain. So make that domain safe BEFORE
                    # propagating, exactly as the non-protocol path does: finish
                    # the untap deterministically, and if repair cannot be
                    # proven complete latch _operational_dirty so the
                    # post-exception resync cannot report the executor synced
                    # over half-untapped operational state (uncleared summoning
                    # sickness, unreset land plays — neither read by
                    # compare_state).
                    #
                    # The fallback can itself raise (protocol or otherwise); a
                    # secondary recovery exception must not replace the primary
                    # untap exception (that would corrupt its classification),
                    # so its propagation is contained here — on any fallback
                    # exception the domain is latched dirty (fail-closed) and the
                    # ORIGINAL untap exception is the one re-raised.
                    try:
                        self._operational_dirty = not self._fallback_untap()
                    except Exception:
                        self._operational_dirty = True
                    raise
                # untap_step is pure engine bookkeeping, but a broken (or
                # monkeypatched) implementation can partially mutate state —
                # untap some permanents, half-clear summoning sickness — and
                # then raise. Record the ENGINE_ERROR (this transition started
                # clean, so it is honestly attributable here), then finish the
                # untap DETERMINISTICALLY rather than re-run the failing entry
                # point: _fallback_untap re-does the same three invariants with
                # idempotent attribute writes. If even that cannot complete,
                # latch the operational-state domain dirty so the recovery
                # barrier suppresses every later transition (the fail-closed
                # floor). Operational dirtiness is tracked separately from
                # _synced precisely so the post-step P/T resync — which sets
                # _synced True — can never erase it.
                self._record_engine_failure(
                    result,
                    f"turn-boundary untap: {type(exc).__name__}: {exc}",
                )
                self._operational_dirty = not self._fallback_untap(result)
            else:
                # A clean untap leaves every untap invariant restored, so the
                # operational domain is clean. Set explicitly for symmetry with
                # the failure path — _operational_dirty is only ever raised on
                # that path, and a raised latch suppresses every later step
                # (its _handle_turn_info, and so this untap, never re-runs), so
                # in the normal flow this is a reaffirming no-op.
                self._operational_dirty = False

        phase_name = self._GRE_PHASE_TO_ENGINE.get(curr_turn.phase)
        if phase_name is not None:
            self.game.phase = Phase(phase_name)
        step_name = self._GRE_STEP_TO_ENGINE.get(curr_turn.step)
        self.game.step = Step(step_name) if step_name is not None else None

        if curr_turn.step != prev_turn.step:
            self._fire_step_events(curr_turn, result)

        # Mana pools are no longer emptied here on every phase/step transition.
        # _execute_step_simulate SETs each pool to GRE's attested manaPool
        # (_sync_mana_pools) every snapshot, so the pool empties exactly when
        # GRE attests it empty and floating mana carries exactly as far as GRE
        # holds it — the window bound is whatever GRE attests, not a guessed
        # transition rule. Observer mode never funds a pool, so nothing to do.

    def _fallback_untap(self, result: StepResult | None = None) -> bool:
        """Deterministically restore untap invariants after ``untap_step`` raised.

        The engine untap step is three operations on the active player: untap
        every permanent they control, clear its summoning sickness, and reset
        ``land_plays_remaining`` to 1. A broken implementation may complete some
        of these and then raise, leaving state half-untapped. This re-does
        exactly those operations directly — NOT by calling ``untap_step`` again
        (which would re-hit the same failing path), but with idempotent
        attribute writes: setting ``is_tapped``/``summoning_sick`` False and
        ``land_plays_remaining`` to 1 is safe whether or not the original run
        already applied it, so a partially completed untap is finished rather
        than retried. That idempotency is what makes recovery well-defined.

        The writes touch no card code, so they cannot re-trigger the original
        crash; the only way they fail is an exotic engine-object error, which is
        recorded and reported as False so the caller latches operational
        dirtiness (the fail-closed path). A protocol exception mid-repair
        latches operational dirtiness ITSELF before propagating (fail-closed):
        reaching the handler means the invariants are unproven, and the caller's
        ``_operational_dirty = not _fallback_untap(...)`` assignment never runs
        when this raises, so without the latch a later P/T resync could report
        the executor synced over half-untapped state. Classification is
        preserved — the protocol exception propagates unchanged.

        Returns True when all invariants were restored, False otherwise.
        """
        if self.game is None:
            return True
        from engine.types import Zone

        try:
            active = self.game.active_player
            for card in active.zones[Zone.BATTLEFIELD].get_all():
                if hasattr(card, "is_tapped"):
                    card.is_tapped = False
                if hasattr(card, "summoning_sick"):
                    card.summoning_sick = False
            active.land_plays_remaining = 1
            return True
        except Exception as exc:
            if _is_protocol_exception(exc):
                # Fail-closed: reaching here means the idempotent writes did NOT
                # all complete (the sole success path returns True with every
                # invariant restored), so the untap invariants are unproven.
                # Latch the operational domain dirty BEFORE propagating —
                # otherwise the caller's `_operational_dirty =
                # not _fallback_untap(...)` assignment never runs (the exception
                # propagates through it) and the post-exception P/T resync would
                # report the executor synced while summoning sickness / land
                # plays stay unrestored. Classification is preserved: the
                # protocol exception propagates unchanged.
                self._operational_dirty = True
                raise
            self._record_engine_failure(
                result,
                f"untap fallback: {type(exc).__name__}: {exc}",
            )
            return False

    def _replay_cleanup(self) -> None:
        """The mechanical part of the cleanup step, at the GRE turn boundary.

        Runs the engine's :func:`~engine.turn.cleanup_mechanical` (rule 514
        steps 2-5) — without the discard (GRE zone moves drive discards
        explicitly) and without the SBA/priority loop (deaths are
        GRE-observed events, not for the replay layer to invent at a
        boundary GRE shows none).

        Skipped once the effect layer is known broken: cleanup_mechanical
        leads with ``apply_all``, which would only re-crash. Skipping it keeps
        the caller from re-triggering the same failing card-code path at every
        turn boundary (the game is already unmeasurable and suppressed).
        """
        if self._effects_broken:
            return
        from engine.turn import cleanup_mechanical

        cleanup_mechanical(self.game)

    def _fire_step_events(self, curr_turn: TurnInfo, result: StepResult | None) -> None:
        """Fire turn-structure trigger events at GRE step boundaries.

        The engine fires these from run_turn, which replay never uses — it
        follows the GRE step sequence instead, so upkeep/begin-combat/end-
        step triggered abilities must be fired here or they never trigger.
        fire_event pushes matching triggers onto the engine stack; GRE's
        ability_resolution actions (or the pre-resync flush) resolve them.
        """
        from engine.events import (
            BeginningOfCombatTriggeredEvent,
            BeginningOfUpkeepTriggeredEvent,
            EndOfTurnTriggeredEvent,
            EndStepTriggeredEvent,
        )

        step = curr_turn.step
        try:
            if step == "Step_Upkeep":
                self.game.trigger_manager.fire_event(
                    self.game, BeginningOfUpkeepTriggeredEvent()
                )
            elif step == "Step_BeginCombat":
                self.game.trigger_manager.fire_event(
                    self.game, BeginningOfCombatTriggeredEvent()
                )
            elif step == "Step_End":
                self.game.trigger_manager.fire_event(
                    self.game,
                    EndStepTriggeredEvent(player=self.game.active_player),
                )
                self.game.trigger_manager.fire_event(
                    self.game, EndOfTurnTriggeredEvent()
                )
        except Exception as exc:
            if result is not None:
                result.infra_failures.append(
                    f"step event ({step}): {type(exc).__name__}: {exc}"
                )
            else:
                logger.debug("step event firing failed", exc_info=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_card_by_grp_id(self, cards: list[Any], grp_id: int) -> Any | None:
        """Find a card in a list by grpId."""
        for card in cards:
            if getattr(card, "_grp_id", 0) == grp_id:
                return card
            # Also check by card name
            card_name = self._grp_to_name.get(grp_id, "")
            if card_name and getattr(card, "name", "") == card_name:
                return card
        return None

    def _find_card_by_name(self, cards: list[Any], name: str) -> Any | None:
        """Find a card in a list by name."""
        for card in cards:
            if getattr(card, "name", "") == name:
                return card
        return None

    def _card_to_grp_id(self, card: Any) -> int:
        """Get the grpId for an engine card."""
        grp = getattr(card, "_grp_id", 0)
        if grp:
            return grp
        # Reverse lookup by name
        name = getattr(card, "name", "")
        for gid, n in self._grp_to_name.items():
            if n == name:
                return gid
        return 0

    @property
    def step_count(self) -> int:
        """Number of steps executed so far."""
        return len(self.results)

    @property
    def all_matched(self) -> bool:
        """True if all executed steps had matching state."""
        return all(r.matched for r in self.results if not r.skipped)
