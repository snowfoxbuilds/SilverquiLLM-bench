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
    ) -> list[tuple[Any, int, str, list[Any]]]:
        """Group a snapshot's zone objects per (engine zone, seat).

        Returns ``(engine_zone, seat_id, gre_zone_type, objects)`` tuples.
        Per-seat GRE zones (hand, library, graveyard) yield one group each.
        Shared GRE zones (battlefield, exile, stack — ``ownerSeatId == 0``)
        are split into one group per known player, routing each object by its
        controller (battlefield) or owner seat, so they line up with the
        engine's per-player zone model. Empty groups are included so callers
        can detect engine-side excess cards.
        """
        from engine.types import Zone

        groups: list[tuple[Any, int, str, list[Any]]] = []
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
                groups.append((engine_zone, snap_zone.owner_seat_id, snap_zone.type, objs))
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
                groups.append((engine_zone, seat, snap_zone.type, group))
        return groups

    def _rebuild_instance_map(self, snapshot: GameSnapshot) -> None:
        """Rebuild the GRE instanceId -> engine card mapping."""
        self._engine_cards.clear()

        for engine_zone_enum, seat_id, zone_type_str, objs in self._snapshot_zone_groups(snapshot):
            if zone_type_str in ("ZoneType_Library", "ZoneType_Stack"):
                continue  # hidden identities / game-level stack — nothing to correlate
            player = self.players.get(seat_id)
            if player is None:
                continue

            engine_cards = player.zones[engine_zone_enum].get_all()

            # Match by grpId (card name) in order
            grp_id_cards: dict[int, list[Any]] = {}
            for card in engine_cards:
                grp = getattr(card, "_grp_id", 0)
                if grp == 0:
                    # Try to find grpId from card name
                    for gid, name in self._grp_to_name.items():
                        if name == card.name:
                            grp = gid
                            break
                grp_id_cards.setdefault(grp, []).append(card)

            for obj in objs:
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

        # Detect phase/step changes
        self._handle_turn_info(prev_snapshot.turn_info, curr_snapshot.turn_info)

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
        actions = actions + self._infer_hidden_origin_actions(
            actions, prev_snapshot, curr_snapshot
        )

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
        result.success = not result.mismatches and not result.engine_failures

        # Oracle-resync to GRE truth so the next step starts clean.
        self._resync_to_snapshot(curr_snapshot)

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
                try:
                    combat_damage_step(self.game, sub_step=sub_step)
                except Exception as exc:
                    result.engine_failures.append(
                        f"combat_damage_step: {type(exc).__name__}: {exc}"
                    )

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
                drawn = draw_card(self.game, player)
                if drawn is None:
                    result.engine_failures.append(
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
        start = self._gsid_index.get(curr_snapshot.game_state_id, 0)
        for snap in self.replay.snapshots[start : start + 30]:
            for ann in snap.annotations:
                if (
                    "AnnotationType_ManaPaid" in ann.type
                    and spell_iid in ann.affected_ids
                ):
                    # Credit only — the tap lands at the annotation's home
                    # snapshot, when GRE also shows the source tapped.
                    self._apply_one_mana_payment(ann, tap=False)
            # Stop once the spell has left the stack (resolved/countered).
            if snap.game_state_id > curr_snapshot.game_state_id and spell_iid not in snap.game_objects:
                break

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
        """Build intent preferences from GRE PlayerSubmittedTargets.

        Each submitted target id maps to the correlated engine object (bound
        by the engine-minted instance id, the one dynamically-bound field) or
        an engine player (bound by seat). A name-based preference follows each
        instance preference as a fallback, and the greedy preference scan
        takes the first that matches an offered option.
        """
        from engine.decisions import Decision

        target_ids: list[int] = []
        # Targets are submitted while the spell is on the stack — scan the
        # cast snapshot, one snapshot back, then forward while it's pending.
        candidates: list[GameSnapshot] = [prev_snapshot]
        start = self._gsid_index.get(curr_snapshot.game_state_id)
        if start is not None:
            candidates.extend(self.replay.snapshots[start : start + 30])
        else:
            candidates.append(curr_snapshot)
        for snap in candidates:
            for ann in snap.annotations:
                if (
                    "AnnotationType_PlayerSubmittedTargets" in ann.type
                    and ann.affector_id == seat
                ):
                    target_ids.extend(ann.affected_ids)
            if target_ids:
                break
            if (
                spell_iid
                and snap.game_state_id > curr_snapshot.game_state_id
                and spell_iid not in snap.game_objects
            ):
                break  # spell left the stack — later targets belong to others

        preferences: list[Any] = []
        for tid in target_ids:
            if tid in self.players:
                preferences.append(Decision.player(seat=tid))
                continue
            target = self._engine_cards.get(tid)
            if target is None:
                continue
            engine_iid = self._engine_instance_id(target)
            if engine_iid is not None:
                preferences.append(Decision.obj(instance=engine_iid))
            name = getattr(target, "name", "")
            if name:
                preferences.append(Decision.obj(name=name))
        return tuple(preferences)

    def _engine_instance_id(self, card: Any) -> int | None:
        """The engine-minted instance id for *card* in its current zone."""
        if self.game is None or not hasattr(self.game, "refs"):
            return None
        for player in self.game.players:
            for zone, container in player.zones.items():
                if container.contains(card):
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
            result.success = False
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
        items = self.game.stack._items
        for i in range(len(items) - 1, -1, -1):
            if items[i].source is card:
                stack_obj = items.pop(i)
                stack_obj.on_resolve(self.game)
                return True
        return False

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

        if action.source_zone == "ZoneType_Stack" and card is not None:
            # Spell resolution — run the queued engine resolution if present.
            if self._resolve_stack_object_for(card):
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

    def _simulate_ability_resolution(
        self,
        action: ReplayAction,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
        result: StepResult,
    ) -> None:
        """Resolve a pending engine trigger when GRE resolves the ability.

        Engine triggers push StackObjects when events fire; GRE reports the
        resolution as this action. If the engine queued a matching trigger,
        resolve it now — otherwise outcome validation applies: a missed
        effect shows up in the state comparison, not as a patched value.
        """
        if action.action_type == "ability_activation":
            if action.instance_id in curr_snapshot.game_objects:
                return  # still on the GRE stack; resolve when it leaves

        source_card = self._find_ability_source(action)
        if source_card is not None:
            self._resolve_stack_object_for(source_card)

    def _resync_to_snapshot(self, snapshot: GameSnapshot) -> None:
        """Oracle-correct engine state to the GRE snapshot (post-comparison).

        Corrects everything compare_state() checks — zone contents, life
        totals, tapped state, and P/T (via base-stat adjustment, the lever
        that survives EffectManager.apply_all resets) — so a divergence is
        reported exactly once and later steps validate independently.
        """
        # GRE's stack is empty but the engine still queues stack objects:
        # resolve them now (late) — Arena auto-resolves triggers without
        # distinct stack steps, so pending effects must land before sync.
        if self.game is not None:
            gre_stack_empty = not any(
                zone.object_instance_ids
                for zone in snapshot.zones.values()
                if zone.type == "ZoneType_Stack"
            )
            if gre_stack_empty:
                guard = 0
                while not self.game.stack.is_empty() and guard < 50:
                    guard += 1
                    stack_obj = self.game.stack.pop()
                    try:
                        stack_obj.on_resolve(self.game)
                    except Exception:
                        logger.debug("late stack resolution failed", exc_info=True)

        self._sync_zones(snapshot)

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
            if obj.power is not None and hasattr(card, "base_power"):
                delta = obj.power - getattr(card, "power", card.base_power)
                if delta:
                    card.base_power += delta
                    card.modified_power = getattr(card, "modified_power", 0) + delta
            if obj.toughness is not None and hasattr(card, "base_toughness"):
                delta = obj.toughness - getattr(card, "toughness", card.base_toughness)
                if delta:
                    card.base_toughness += delta
                    card.modified_toughness = getattr(card, "modified_toughness", 0) + delta

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

        for engine_zone_enum, seat_id, zone_type_str, objs in self._snapshot_zone_groups(snapshot):
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
            # Search the controller's battlefield first, then all players
            seats = []
            if action.player_seat_id:
                seats.append(action.player_seat_id)
            seats.extend(s for s in self.players if s != action.player_seat_id)
            for seat_id in seats:
                player = self.players.get(seat_id)
                if player is None:
                    continue
                card = self._find_card_by_grp_id(
                    player.zones[Zone.BATTLEFIELD].get_all(), action.grp_id
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

    def _sync_zones(self, snapshot: GameSnapshot) -> None:
        """Sync engine zones with snapshot for cards that appeared without
        tracked ObjectIdChanged annotations (opening hands, mulligans, etc.).

        Compares grpId multisets per zone. Injects missing cards into the
        engine and removes excess cards. Library and Stack are skipped.
        """
        # Library: hidden and order-dependent, inferred via draw actions.
        # Stack: transient; engine models entries differently than GRE.
        SKIP_ZONES = {"ZoneType_Library", "ZoneType_Stack"}

        for engine_zone_enum, seat_id, zone_type_str, objs in self._snapshot_zone_groups(snapshot):
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
                        if hasattr(card, "register_triggers"):
                            card.register_triggers(self.game)
                        if hasattr(card, "register_replacement_effects"):
                            card.register_replacement_effects(self.game)
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
            # excess — remove them or they diverge forever.
            engine_cards_list = player.zones[engine_zone_enum].get_all()
            overflow = len(engine_cards_list) - len(objs)
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

    def _remove_synced_card(
        self, player: Any, engine_zone: Any, card: Any, is_battlefield: bool
    ) -> None:
        """Remove a card during zone sync, with trigger cleanup on battlefield."""
        player.zones[engine_zone].remove(card)
        if self.simulate and is_battlefield and self.game is not None:
            # Symmetric cleanup — stale triggers must not keep firing for a
            # permanent GRE says is gone.
            self.game.trigger_manager.unregister(card)
            self.game.replacement_manager.unregister(card)

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

    def _handle_turn_info(self, prev_turn: TurnInfo, curr_turn: TurnInfo) -> None:
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
            # New turn: engine untap step for the (already updated) active
            # player — untap, clear summoning sickness, reset land plays.
            from engine.turn import _do_untap_step
            _do_untap_step(self.game)

        phase_name = self._GRE_PHASE_TO_ENGINE.get(curr_turn.phase)
        if phase_name is not None:
            self.game.phase = Phase(phase_name)
        step_name = self._GRE_STEP_TO_ENGINE.get(curr_turn.step)
        self.game.step = Step(step_name) if step_name is not None else None

        # Mana pools empty as steps and phases end. Casting pays costs
        # atomically within a step, so emptying on every transition is safe.
        if (curr_turn.phase, curr_turn.step) != (prev_turn.phase, prev_turn.step):
            for player in self.players.values():
                pool = getattr(player, "mana_pool", None)
                if pool is not None:
                    pool.empty()

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
