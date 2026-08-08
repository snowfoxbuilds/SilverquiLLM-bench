"""Replay executor with state-diff observer mode.

Steps through GameSnapshot objects from the parser and validates engine
behavior using state-diff comparison. Seat 1 (17lands user) gets full
validation; Seat 2 (opponent) uses oracle injection.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    ) -> None:
        self.replay = replay
        self.card_id_map = card_id_map or {}
        self.registry = registry
        self.strict = strict
        # Simulation mode: drive gameplay through the engine (casting, combat,
        # mana) and compare state BEFORE resyncing. Default (False) is the
        # original observer mode that oracle-syncs state before comparison.
        self.simulate = simulate

        # Engine state (initialized from first snapshot)
        self.game: Any | None = None
        self.players: dict[int, Any] = {}  # seat_id -> engine Player

        # Tracking: grpId instance -> engine card object
        self._engine_cards: dict[int, Any] = {}  # GRE instanceId -> engine card
        self._grp_to_name: dict[int, str] = dict(self.card_id_map)

        # Tracks which engine cards have had register_triggers applied (prevents double-apply)
        self._triggers_registered: set[int] = set()

        # Simulate mode: the snapshot currently being executed (for handlers
        # that need GRE object data, e.g. hand materialization).
        self._current_snapshot: GameSnapshot | None = None
        # Mana payment annotations already replicated (Arena streams them
        # after the cast event; the cast handler applies them by look-ahead
        # and this set keeps the per-snapshot pass from re-applying).
        self._seen_mana_payments: set[int] = set()
        # GRE stack iid -> engine card awaiting resolution. Kept separately
        # from _engine_cards because the instance-map rebuild (each resync)
        # clears that dict and skips stack zones.
        self._pending_stack: dict[int, Any] = {}
        # Combat state machine (simulate mode): one declaration, one block
        # assignment, and one damage pass per GRE damage step per combat.
        self._combat_active: bool = False
        self._combat_blocks_declared: bool = False
        self._combat_damage_passes: set[str] = set()
        # game_state_id -> snapshot list index, for bounded look-ahead.
        self._gsid_index: dict[int, int] = {}

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
        #   _operational_dirty — set when a non-protocol untap failure could not
        #                     be repaired by the deterministic fallback, leaving
        #                     summoning sickness or land plays in an unknown
        #                     state. compare_state never reads those surfaces, so
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
                if drawn is None:
                    result.infra_failures.append(
                        f"draw (seat {seat}): engine library empty"
                    )
                    continue
                obj = curr_snapshot.game_objects.get(iid)
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

    def _apply_mana_payments(self, snapshot: GameSnapshot, result: StepResult) -> None:
        """Replicate ManaPaid annotations: tap the source, credit the pool.

        ``affectorId`` is the paying permanent's GRE instance id; ``color``
        is the Arena color enum. The payer's pool is credited so the
        subsequent cast_spell in this step can pay its cost; pools empty at
        the next step transition, so overshoot never leaks across steps.
        """
        for ann in snapshot.annotations:
            if "AnnotationType_ManaPaid" not in ann.type:
                continue
            self._apply_one_mana_payment(ann)

    def _apply_one_mana_payment(self, ann: Any, tap: bool = True) -> None:
        """Credit the payer's pool (once per annotation) and tap the source.

        The pool credit is deduped by annotation id — a cast's look-ahead
        may have credited it already. The tap is NOT applied by look-ahead
        (``tap=False``): GRE shows the land tapped only in the annotation's
        home snapshot, so tapping early would mis-compare that snapshot and
        the dedup would then leave the land untapped when GRE taps it. The
        per-snapshot pass taps at exactly the GRE-observed moment.
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
        try:
            cast_spell(self.game, player, card)
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

    def _resolve_stack_object_for(self, card: Any) -> bool:
        """Resolve the engine StackObject whose source is *card*, if any."""
        if self.game is None:
            return False
        stack_obj = self.game.stack.pop_by_source(card)
        if stack_obj is None:
            return False
        stack_obj.on_resolve(self.game)
        return True

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
        if orig_iid is not None:
            card = self._pending_stack.pop(orig_iid, None) or self._engine_cards.get(orig_iid)
        if card is None:
            card = self._pending_stack.pop(action.instance_id, None) or self._engine_cards.get(action.instance_id)

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
            try:
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

        player = self.players.get(action.player_seat_id) or getattr(card, "owner", None)
        if player is None or self.game is None:
            return
        src = _GRE_ZONE_TO_ENGINE.get(action.source_zone)
        try:
            self._with_target_intent(
                action, prev_snapshot, curr_snapshot,
                lambda: cast_spell_free(self.game, player, card, Zone(src)),
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

    def _try_activate_ability(
        self,
        player: Any,
        source_card: Any,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Activate *source_card*'s single activated ability, if unambiguous.

        GRE does not say which of a card's abilities an ability object is,
        so only the one-ability case is driven; multi-ability sources fall
        through to the resync (recorded by state comparison, not guessed).
        """
        try:
            abilities = list(source_card.get_activated_abilities() or [])
        except Exception:
            abilities = []
        if len(abilities) != 1:
            return
        from engine.abilities import ActivatedAbilityInstance, activate_ability

        instance = ActivatedAbilityInstance(
            source=source_card,
            controller=player,
            cost=abilities[0].cost,
            effect=abilities[0].effect,
            is_mana_ability=False,
            description=abilities[0].description,
        )
        name = action.card_name or getattr(source_card, "name", "?")
        try:
            self._with_target_intent(
                action, prev_snapshot, curr_snapshot,
                lambda: activate_ability(self.game, player, instance),
            )
        except Exception as exc:
            result.engine_failures.append(
                f"activate_ability {name} (seat {action.player_seat_id}): "
                f"{type(exc).__name__}: {exc}"
            )

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

        def residual_deltas() -> list[tuple[Any, int, int]]:
            deltas: list[tuple[Any, int, int]] = []
            for obj in snapshot.get_zone_objects("ZoneType_Battlefield"):
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

        # Mana pools empty as steps and phases end. Casting pays costs
        # atomically within a step, so emptying on every transition is safe.
        if (curr_turn.phase, curr_turn.step) != (prev_turn.phase, prev_turn.step):
            for player in self.players.values():
                pool = getattr(player, "mana_pool", None)
                if pool is not None:
                    pool.empty()

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
        dirtiness (the fail-closed path). Protocol exceptions propagate.

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
