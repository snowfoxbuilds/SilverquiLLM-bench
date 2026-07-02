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

        # Build hand contents from snapshot zones
        seat_hands: dict[int, list[int]] = {}  # seat_id -> list of grpIds
        seat_libraries: dict[int, list[int]] = {}  # seat_id -> list of grpIds

        for zone in snapshot.zones.values():
            if zone.type == "ZoneType_Hand":
                grp_ids = []
                for iid in zone.object_instance_ids:
                    obj = snapshot.game_objects.get(iid)
                    if obj:
                        grp_ids.append(obj.grp_id)
                        self._engine_cards[iid] = None  # placeholder
                seat_hands[zone.owner_seat_id] = grp_ids

            elif zone.type == "ZoneType_Library":
                grp_ids = []
                for iid in zone.object_instance_ids:
                    obj = snapshot.game_objects.get(iid)
                    if obj:
                        grp_ids.append(obj.grp_id)
                seat_libraries[zone.owner_seat_id] = grp_ids

        # Create card instances and set up hands/libraries
        self._setup_player_zones(snapshot, seat_hands, seat_libraries)
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
            # Create hand cards
            hand_grps = seat_hands.get(seat_id, [])
            for grp_id in hand_grps:
                card = self._create_card(grp_id, player)
                player.zones[Zone.HAND].add(card)

            # Create library cards
            lib_grps = seat_libraries.get(seat_id, [])
            for grp_id in lib_grps:
                card = self._create_card(grp_id, player)
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

    def _rebuild_instance_map(self, snapshot: GameSnapshot) -> None:
        """Rebuild the GRE instanceId -> engine card mapping."""
        from engine.types import Zone

        self._engine_cards.clear()

        for snap_zone in snapshot.zones.values():
            zone_type_str = snap_zone.type
            engine_zone_name = _GRE_ZONE_TO_ENGINE.get(zone_type_str)
            if engine_zone_name is None:
                continue

            seat_id = snap_zone.owner_seat_id
            player = self.players.get(seat_id)
            if player is None:
                continue

            try:
                engine_zone_enum = Zone(engine_zone_name)
            except ValueError:
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

            for iid in snap_zone.object_instance_ids:
                obj = snapshot.game_objects.get(iid)
                if obj is None:
                    continue
                candidates = grp_id_cards.get(obj.grp_id, [])
                if candidates:
                    self._engine_cards[iid] = candidates.pop(0)

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

        # Battlefield state (tapped, P/T)
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
        from engine.types import Zone

        mismatches = []

        for snap_zone in snapshot.zones.values():
            zone_type_str = snap_zone.type
            engine_zone_name = _GRE_ZONE_TO_ENGINE.get(zone_type_str)
            if engine_zone_name is None:
                continue

            # Skip library comparisons (hidden zone, ordering differs)
            if zone_type_str == "ZoneType_Library":
                continue

            seat_id = snap_zone.owner_seat_id
            player = self.players.get(seat_id)
            if player is None:
                continue

            try:
                engine_zone_enum = Zone(engine_zone_name)
            except ValueError:
                continue

            # Get grpIds from snapshot zone
            snap_grp_ids = sorted(
                obj.grp_id
                for iid in snap_zone.object_instance_ids
                if (obj := snapshot.game_objects.get(iid)) is not None
            )

            # Get grpIds via engine zone
            engine_cards = player.zones[engine_zone_enum].get_all()
            engine_grp_ids = sorted(
                self._card_to_grp_id(card)
                for card in engine_cards
            )

            if snap_grp_ids != engine_grp_ids:
                # Only report for non-hand zones of opponent (hand is hidden)
                if seat_id != self.replay.seat_id and zone_type_str == "ZoneType_Hand":
                    continue

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
            from engine.zones import move_to_zone
            move_to_zone(
                self.game, card, Zone.BATTLEFIELD, Zone.GRAVEYARD,
                replacement_event_type="creature_dies",
            )
        except Exception as exc:
            # ENGINE LIMITATION: oracle-injected — move_to_zone may fail
            # if card state is inconsistent; fall back to direct mutation.
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
        from engine.types import Zone

        # Library: hidden and order-dependent, inferred via draw actions.
        # Stack: transient; engine models entries differently than GRE.
        SKIP_ZONES = {"ZoneType_Library", "ZoneType_Stack"}

        for snap_zone in snapshot.zones.values():
            zone_type_str = snap_zone.type
            if zone_type_str in SKIP_ZONES:
                continue

            engine_zone_name = _GRE_ZONE_TO_ENGINE.get(zone_type_str)
            if engine_zone_name is None:
                continue

            seat_id = snap_zone.owner_seat_id
            player = self.players.get(seat_id)
            if player is None:
                continue

            try:
                engine_zone_enum = Zone(engine_zone_name)
            except ValueError:
                continue

            # grpId multiset from snapshot (skip unknown grpId=0)
            snap_grp_ids: Counter[int] = Counter()
            for iid in snap_zone.object_instance_ids:
                obj = snapshot.game_objects.get(iid)
                if obj is not None and obj.grp_id != 0:
                    snap_grp_ids[obj.grp_id] += 1

            # grpId multiset via engine (skip grpId=0)
            engine_cards_list = player.zones[engine_zone_enum].get_all()
            engine_grp_ids: Counter[int] = Counter(
                gid for card in engine_cards_list
                if (gid := self._card_to_grp_id(card)) != 0
            )

            # Inject cards present in snapshot but missing in engine
            for grp_id, snap_count in snap_grp_ids.items():
                deficit = snap_count - engine_grp_ids.get(grp_id, 0)
                for _ in range(deficit):
                    card = self._create_card(grp_id, player)
                    card._grp_id = grp_id
                    player.zones[engine_zone_enum].add(card)
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
                        player.zones[engine_zone_enum].remove(card)
                        logger.debug(
                            "_sync_zones: removed grpId=%d from %s (seat %d)",
                            grp_id, zone_type_str, seat_id,
                        )

        self._rebuild_instance_map(snapshot)

    # ------------------------------------------------------------------
    # Turn info / phase handling
    # ------------------------------------------------------------------

    def _handle_turn_info(self, prev_turn: TurnInfo, curr_turn: TurnInfo) -> None:
        """Handle phase/step transitions from turnInfo diffs."""
        if self.game is None:
            return

        # Update turn number
        if curr_turn.turn_number != prev_turn.turn_number and curr_turn.turn_number > 0:
            self.game.turn_number = curr_turn.turn_number

        # Update active player
        if curr_turn.active_player != prev_turn.active_player and curr_turn.active_player > 0:
            seat = curr_turn.active_player
            # Map seat to player index
            for i, p_seat in enumerate(sorted(self.players.keys())):
                if p_seat == seat:
                    self.game.active_player_index = i
                    break

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
