"""Simulate-mode replay validation: mechanism tests + golden game.

These run in the MSH workspace context (``engine`` resolves to this
workspace), like the rest of engine_tests/ — the simulate executor drives
this engine, so its mechanisms are pinned here rather than in the
engine-agnostic root suite.

Mechanism tests build tiny synthetic GRE snapshots and exercise one executor
behavior each, so a regression in (say) the mana look-ahead cannot hide
behind movement in another mechanism the way it could in corpus totals.
The golden-game test runs the full pipeline over a committed corpus game and
pins its divergence fingerprint.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.replay.executor import ReplayExecutor, StepResult
from silverquillm.replay.types import (
    Annotation,
    GameObject,
    GameSnapshot,
    PlayerInfo,
    ReplayAction,
    ReplayGame,
    TurnInfo,
    Zone,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

# Stable FDN grpIds (from data/replays/card_id_map.json).
PLAINS, ISLAND, FOREST = 95192, 95194, 95200
CARD_MAP = {PLAINS: "Plains", ISLAND: "Island", FOREST: "Forest"}

# Synthetic instance-id blocks: zones 11-16, cards 100+, annotations 900+.
HAND1, LIB1, BF1 = 11, 12, 13
HAND2, LIB2, BF2 = 14, 15, 16


def snapshot(
    gsid: int,
    *,
    turn: int = 1,
    phase: str = "Phase_Main1",
    step: str = "",
    active: int = 1,
    hands: dict[int, list[int]] | None = None,
    libraries: dict[int, list[int]] | None = None,
    battlefield: dict[int, list[int]] | None = None,
    objects: dict[int, GameObject] | None = None,
    annotations: list[Annotation] | None = None,
) -> GameSnapshot:
    """Build a two-player snapshot from per-seat zone id lists."""
    hands = hands or {1: [], 2: []}
    libraries = libraries or {1: [], 2: []}
    battlefield = battlefield or {1: [], 2: []}
    snap = GameSnapshot(
        game_state_id=gsid,
        turn_info=TurnInfo(phase=phase, step=step, turn_number=turn, active_player=active),
    )
    snap.players = {1: PlayerInfo(seat_id=1), 2: PlayerInfo(seat_id=2)}
    zone_ids = {(("ZoneType_Hand"), 1): HAND1, ("ZoneType_Hand", 2): HAND2,
                ("ZoneType_Library", 1): LIB1, ("ZoneType_Library", 2): LIB2}
    for seat in (1, 2):
        snap.zones[zone_ids[("ZoneType_Hand", seat)]] = Zone(
            zone_id=zone_ids[("ZoneType_Hand", seat)], type="ZoneType_Hand",
            owner_seat_id=seat, object_instance_ids=list(hands.get(seat, [])),
        )
        snap.zones[zone_ids[("ZoneType_Library", seat)]] = Zone(
            zone_id=zone_ids[("ZoneType_Library", seat)], type="ZoneType_Library",
            owner_seat_id=seat, object_instance_ids=list(libraries.get(seat, [])),
        )
    # Shared battlefield (ownerSeatId=0), objects routed by controller.
    snap.zones[BF1] = Zone(
        zone_id=BF1, type="ZoneType_Battlefield", owner_seat_id=0,
        object_instance_ids=list(battlefield.get(1, [])) + list(battlefield.get(2, [])),
    )
    for iid, obj in (objects or {}).items():
        snap.game_objects[iid] = obj
    snap.annotations = list(annotations or [])
    return snap


def card_obj(iid: int, grp: int, seat: int, zone_id: int, **kw) -> GameObject:
    return GameObject(
        instance_id=iid, grp_id=grp, type="GameObjectType_Card",
        zone_id=zone_id, owner_seat_id=seat, controller_seat_id=seat,
        visibility="Visibility_Public", **kw,
    )


def make_executor(snapshots: list[GameSnapshot]) -> ReplayExecutor:
    replay = ReplayGame(seat_id=1, opponent_seat_id=2)
    replay.snapshots = snapshots
    ex = ReplayExecutor(replay=replay, card_id_map=dict(CARD_MAP), registry=None, simulate=True)
    ex.initialize(snapshots[0])
    # initialize() builds hands/libraries; battlefield objects in the first
    # snapshot enter (and correlate) through the zone sync, as in real games.
    ex._sync_zones(snapshots[0])
    return ex


def id_change(ann_id: int, orig: int, new: int) -> Annotation:
    return Annotation(
        id=ann_id, type=["AnnotationType_ObjectIdChanged"],
        details={"orig_id": [orig], "new_id": [new]},
    )


class TestManaLookahead:
    def test_payment_after_object_deletion_still_credits(self):
        """ManaPaid streamed after the funded object left game_objects counts.

        Arena pays "late" for fast auto-resolves (equips, quick sorceries);
        the look-ahead must not cut its window at the object's deletion.
        """
        from engine.types import ManaType

        land = card_obj(100, FOREST, 1, BF1, card_types=["CardType_Land"])
        s0 = snapshot(1, battlefield={1: [100]}, objects={100: land})
        # Spell object 200 exists only at gsid 2; payment streams at gsid 4.
        s1 = snapshot(2, battlefield={1: [100]}, objects={100: land})
        s2 = snapshot(3, battlefield={1: [100]}, objects={100: land})
        pay = Annotation(
            id=901, affector_id=100, affected_ids=[200],
            type=["AnnotationType_ManaPaid"], details={"id": [901], "color": [5]},
        )
        s3 = snapshot(4, battlefield={1: [100]}, objects={100: land}, annotations=[pay])
        ex = make_executor([s0, s1, s2, s3])

        ex._apply_spell_mana_lookahead(200, s1)
        pool = ex.players[1].mana_pool
        assert pool.total() == 1
        # Look-ahead credits only; the tap belongs to the payment's own snapshot.
        assert not ex._engine_cards[100].is_tapped

    def test_payment_credited_once(self):
        land = card_obj(100, FOREST, 1, BF1)
        pay = Annotation(
            id=901, affector_id=100, affected_ids=[200],
            type=["AnnotationType_ManaPaid"], details={"id": [901], "color": [5]},
        )
        s0 = snapshot(1, battlefield={1: [100]}, objects={100: land}, annotations=[pay])
        ex = make_executor([s0])
        ex._apply_spell_mana_lookahead(200, s0)
        ex._apply_spell_mana_lookahead(200, s0)
        assert ex.players[1].mana_pool.total() == 1


class TestTargetDerivation:
    def _target_spec(self, ann_id: int, spell: int, targets: list[int], index: int = 1):
        return Annotation(
            id=ann_id, affector_id=spell, affected_ids=targets,
            type=["AnnotationType_TargetSpec"], details={"index": [index]},
        )

    def test_targets_keyed_to_spell_instance(self):
        """Another same-seat spell's TargetSpec must not cross-wire."""
        victim = card_obj(150, FOREST, 2, BF1)
        s0 = snapshot(1, battlefield={2: [150]}, objects={150: victim})
        s1 = snapshot(
            2, battlefield={2: [150]}, objects={150: victim},
            annotations=[
                self._target_spec(902, 200, [150]),      # our spell
                self._target_spec(903, 300, [2]),        # a different spell
            ],
        )
        ex = make_executor([s0, s1])
        prefs = ex._derive_target_preferences(1, s0, s0, spell_iid=200)
        assert len(prefs) >= 1  # resolves 150 (object), not seat 2

        prefs_other = ex._derive_target_preferences(1, s0, s0, spell_iid=300)
        # The other spell targets a player (seat 2).
        assert len(prefs_other) == 1

    def test_no_spell_id_yields_no_preferences(self):
        s0 = snapshot(1)
        ex = make_executor([s0])
        assert ex._derive_target_preferences(1, s0, s0, spell_iid=0) == ()


class TestHiddenOriginActions:
    def test_opponent_stack_arrival_becomes_spell_cast(self):
        s0 = snapshot(1)
        spell = GameObject(
            instance_id=210, grp_id=ISLAND, type="GameObjectType_Card",
            zone_id=99, owner_seat_id=2, controller_seat_id=2,
        )
        s1 = snapshot(2, objects={210: spell})
        s1.zones[99] = Zone(zone_id=99, type="ZoneType_Stack", owner_seat_id=0,
                            object_instance_ids=[210])
        ex = make_executor([s0, s1])
        actions = ex._infer_hidden_origin_actions([], s0, s1)
        assert [(a.action_type, a.player_seat_id, a.instance_id) for a in actions] == [
            ("spell_cast", 2, 210)
        ]

    def test_opponent_battlefield_land_becomes_land_play(self):
        s0 = snapshot(1)
        land = card_obj(211, FOREST, 2, BF1, card_types=["CardType_Land"])
        s1 = snapshot(2, battlefield={2: [211]}, objects={211: land})
        ex = make_executor([s0, s1])
        actions = ex._infer_hidden_origin_actions([], s0, s1)
        assert [(a.action_type, a.instance_id) for a in actions] == [("land_play", 211)]

    def test_covered_and_visible_origin_arrivals_are_skipped(self):
        prev_land = card_obj(211, FOREST, 2, BF1, card_types=["CardType_Land"])
        s0 = snapshot(1, hands={2: [140]})
        land = card_obj(212, FOREST, 2, BF1, card_types=["CardType_Land"])
        s1 = snapshot(
            2, battlefield={2: [212]}, objects={212: land},
            annotations=[id_change(910, 140, 212)],
        )
        ex = make_executor([s0, s1])
        # Covered by an existing action -> skip.
        covering = [ReplayAction(action_type="land_play", instance_id=212)]
        assert ex._infer_hidden_origin_actions(covering, s0, s1) == []
        # Hand origin (even hidden) IS a play; battlefield origin is not.
        actions = ex._infer_hidden_origin_actions([], s0, s1)
        assert len(actions) == 1


class TestDrawClassification:
    def test_library_provenance_arrival_is_drawn(self):
        """The normal GRE draw: library id re-minted into the hand."""
        s0 = snapshot(1, hands={1: [101]}, libraries={1: [102, 103]})
        s1 = snapshot(
            2, hands={1: [101, 130]}, libraries={1: [103]},
            annotations=[id_change(911, 102, 130)],
        )
        ex = make_executor([s0, s1])
        hand_before = len(ex.players[1].zones_hand()) if hasattr(ex.players[1], "zones_hand") else None
        from engine.types import Zone as EZone
        assert len(ex.players[1].zones[EZone.HAND].get_all()) == 1
        ex._simulate_hand_draws(s0, s1, StepResult(snapshot_id=2))
        assert len(ex.players[1].zones[EZone.HAND].get_all()) == 2
        assert len(ex.players[1].zones[EZone.LIBRARY].get_all()) == 1

    def test_bounce_arrival_is_not_drawn(self):
        """A battlefield-origin hand arrival is a zone move, not a draw."""
        from engine.types import Zone as EZone

        perm = card_obj(120, FOREST, 1, BF1)
        s0 = snapshot(1, hands={1: [101]}, libraries={1: [102]},
                      battlefield={1: [120]}, objects={120: perm})
        s1 = snapshot(
            2, hands={1: [101, 131]}, libraries={1: [102]},
            annotations=[id_change(912, 120, 131)],
        )
        ex = make_executor([s0, s1])
        ex._simulate_hand_draws(s0, s1, StepResult(snapshot_id=2))
        # Library untouched: the arrival had a visible battlefield origin.
        assert len(ex.players[1].zones[EZone.LIBRARY].get_all()) == 1

    def test_mulligan_redeal_shuffles_hand_back_first(self):
        from engine.types import Zone as EZone

        s0 = snapshot(1, turn=0, hands={1: [101, 102]}, libraries={1: [103, 104, 105]})
        # Wholesale hand-id replacement before turn 1 = re-deal.
        s1 = snapshot(2, turn=0, hands={1: [140, 141]}, libraries={1: [103, 104, 105]})
        ex = make_executor([s0, s1])
        assert len(ex.players[1].zones[EZone.HAND].get_all()) == 2
        ex._simulate_hand_draws(s0, s1, StepResult(snapshot_id=2))
        # Hand stays at 2 (not 4): the old hand went back to the library.
        assert len(ex.players[1].zones[EZone.HAND].get_all()) == 2
        assert len(ex.players[1].zones[EZone.LIBRARY].get_all()) == 3


class TestOverflowGuard:
    def test_hidden_opponent_hand_shells_survive_sync(self):
        """Regression: hidden objects appear in zone id-lists without
        game_objects entries; their engine shells are residents, not
        overflow to strip."""
        from engine.types import Zone as EZone

        s0 = snapshot(1, hands={2: [141, 142, 143]})
        ex = make_executor([s0])
        assert len(ex.players[2].zones[EZone.HAND].get_all()) == 3
        ex._sync_zones(s0)
        assert len(ex.players[2].zones[EZone.HAND].get_all()) == 3


class TestBlockerDeathOrder:
    def test_dead_first_in_death_order_survivors_last(self):
        b1 = card_obj(161, FOREST, 2, BF1)
        b2 = card_obj(162, FOREST, 2, BF1)
        b3 = card_obj(163, FOREST, 2, BF1)
        objs = {161: b1, 162: b2, 163: b3}
        s0 = snapshot(1, battlefield={2: [161, 162, 163]}, objects=objs)
        s1 = snapshot(2, battlefield={2: [161, 163]}, objects=objs)   # 162 dies first
        s2 = snapshot(3, battlefield={2: [163]}, objects=objs)        # then 161
        ex = make_executor([s0, s1, s2])
        assert ex._blocker_death_order([161, 162, 163], s0) == [162, 161, 163]


class FakeRegistry:
    """Name-membership registry for mechanism tests (create falls to shells)."""

    def __init__(self, names: set[str]) -> None:
        self._names = set(names)

    def __contains__(self, name: str) -> bool:
        return name in self._names

    def create_instance(self, name: str, owner=None):
        raise KeyError(name)  # force the executor's shell fallback


def make_validator(snapshots, registry, card_map=None, simulate=True):
    from silverquillm.replay.validation import ValidatingExecutor

    replay = ReplayGame(seat_id=1, opponent_seat_id=2)
    replay.snapshots = snapshots
    card_map = card_map if card_map is not None else dict(CARD_MAP)
    ex = ReplayExecutor(
        replay=replay, card_id_map=card_map, registry=registry, simulate=simulate
    )
    ex.initialize(snapshots[0])
    ex._sync_zones(snapshots[0])
    return ex, ValidatingExecutor(ex, card_map)


class TestHonestMissingCard:
    """MISSING_CARD counts the full unimplemented surface, deduplicated
    per (game, identity): parser actions, executor-synthesized hidden-origin
    actions, and unmapped/unregistered battlefield arrivals (tokens)."""

    HARE = 95300          # mapped to a name absent from the registry
    TOKEN = 777777        # unmapped grpId (token-style)
    ALT_FOREST = 888888   # unmapped grpId, resolvable as a basic land

    CARD_MAP2 = dict(CARD_MAP) | {HARE: "Hare Apparent"}
    REGISTERED = {"Plains", "Island", "Forest"}

    def _missing(self, validator):
        from silverquillm.replay.validation import DivergenceType

        return [
            d for d in validator.divergences
            if d.divergence_type == DivergenceType.MISSING_CARD
        ]

    def _stack_snap(self, gsid: int, iid: int) -> GameSnapshot:
        spell = GameObject(
            instance_id=iid, grp_id=self.HARE, type="GameObjectType_Card",
            zone_id=99, owner_seat_id=2, controller_seat_id=2,
            card_types=["CardType_Creature"], power=2, toughness=2,
        )
        snap = snapshot(gsid, objects={iid: spell})
        snap.zones[99] = Zone(
            zone_id=99, type="ZoneType_Stack", owner_seat_id=0,
            object_instance_ids=[iid],
        )
        return snap

    def test_synthesized_opponent_cast_counts_once_per_game(self):
        """An unregistered card the opponent casts twice (hidden origin,
        invisible to parser actions) yields exactly one MISSING_CARD."""
        snaps = [
            snapshot(1),
            self._stack_snap(2, 300),
            snapshot(3),
            self._stack_snap(4, 310),  # second cast of the same card
            snapshot(5),
        ]
        _, validator = make_validator(
            snaps, FakeRegistry(self.REGISTERED), card_map=self.CARD_MAP2
        )
        validator.execute_all()
        missing = self._missing(validator)
        assert len(missing) == 1
        assert "Hare Apparent" in missing[0].description

    def test_unmapped_battlefield_arrival_counts_once_as_grp_identity(self):
        """A token-style battlefield arrival (grpId absent from the map) is
        one grpId_<n> MISSING_CARD per game, across leave/re-arrive."""
        token1 = card_obj(400, self.TOKEN, 1, BF1,
                          card_types=["CardType_Creature"], power=1, toughness=1)
        token1.type = "GameObjectType_Token"
        token2 = card_obj(401, self.TOKEN, 1, BF1,
                          card_types=["CardType_Creature"], power=1, toughness=1)
        token2.type = "GameObjectType_Token"
        snaps = [
            snapshot(1),
            snapshot(2, battlefield={1: [400]}, objects={400: token1}),
            snapshot(3),
            snapshot(4, battlefield={1: [401]}, objects={401: token2}),
        ]
        _, validator = make_validator(snaps, FakeRegistry(self.REGISTERED))
        validator.execute_all()
        missing = self._missing(validator)
        assert len(missing) == 1
        assert f"grpId_{self.TOKEN}" in missing[0].description

    def test_alt_printing_basic_arrival_is_not_missing(self):
        """An unmapped grpId that resolves to a registered basic land via
        its subtypes (arbitrary 17lands printings) is not a missing card —
        the executor builds the real registered card for it."""
        land = card_obj(410, self.ALT_FOREST, 1, BF1,
                        card_types=["CardType_Land"], subtypes=["SubType_Forest"])
        snaps = [snapshot(1), snapshot(2, battlefield={1: [410]}, objects={410: land})]
        _, validator = make_validator(snaps, FakeRegistry(self.REGISTERED))
        validator.execute_all()
        assert self._missing(validator) == []

    def test_parser_visible_missing_card_still_counted(self):
        s1 = snapshot(2)
        s1.actions = [ReplayAction(
            action_type="spell_cast", turn_number=1, active_player=1,
            player_seat_id=1, card_name="Hare Apparent", grp_id=self.HARE,
            instance_id=320,
        )]
        _, validator = make_validator(
            [snapshot(1), s1], FakeRegistry(self.REGISTERED), card_map=self.CARD_MAP2
        )
        validator.execute_all()
        missing = self._missing(validator)
        assert len(missing) == 1
        assert "Hare Apparent" in missing[0].description

    def test_observer_mode_counting_is_unchanged(self):
        """Observer mode keeps the original per-occurrence counting and
        never counts battlefield arrivals (source (c) is simulate-gated)."""
        token = card_obj(400, self.TOKEN, 1, BF1,
                         card_types=["CardType_Creature"], power=1, toughness=1)
        token.type = "GameObjectType_Token"

        def acting(gsid):
            snap = snapshot(gsid, battlefield={1: [400]}, objects={400: token})
            snap.actions = [ReplayAction(
                action_type="spell_cast", turn_number=1, active_player=1,
                player_seat_id=1, card_name="Hare Apparent", grp_id=self.HARE,
                instance_id=320 + gsid,
            )]
            return snap

        snaps = [snapshot(1), acting(2), acting(3)]
        _, validator = make_validator(
            snaps, FakeRegistry(self.REGISTERED),
            card_map=self.CARD_MAP2, simulate=False,
        )
        validator.execute_all()
        missing = self._missing(validator)
        # Two occurrences -> two divergences (no dedup), token arrival ignored.
        assert len(missing) == 2
        assert all("Hare Apparent" in d.description for d in missing)


class TestOraclePTCorrections:
    """Resync P/T corrections are revocable ContinuousEffects, not stat bakes.

    A GRE-side P/T delta the engine missed is corrected by a replay-owned
    Layer 7/7c effect that is cleared and re-derived at every resync —
    printed stats (base_*) are never written, so a temporary GRE-side
    effect can never leave permanent residue in the engine's cards.
    """

    CREATURE = 555000  # deliberately unmapped grpId -> Creature shell

    def _bf_snap(self, gsid: int, power: int, toughness: int = 2, *,
                 turn: int = 1, present: bool = True) -> GameSnapshot:
        if not present:
            return snapshot(gsid, turn=turn, battlefield={1: []})
        obj = card_obj(
            100, self.CREATURE, 1, BF1,
            card_types=["CardType_Creature"], power=power, toughness=toughness,
        )
        return snapshot(gsid, turn=turn, battlefield={1: [100]}, objects={100: obj})

    @staticmethod
    def _pt(result: StepResult) -> list:
        return [m for m in result.mismatches if m.category == "power_toughness"]

    def test_missed_temporary_buff_diverges_once_per_transition_without_stat_drift(self):
        """A +1/+0 buff the engine misses: one divergence when it appears,
        none while it holds, one when it expires — and the old equal-and-
        opposite oscillation (from baking the delta into printed stats)
        is gone: base/modified never change, and no correction remains
        once GRE and engine agree again."""
        snaps = [
            self._bf_snap(1, 2),   # engine and GRE agree: 2/2
            self._bf_snap(2, 3),   # GRE-side buff appears (engine missed it)
            self._bf_snap(3, 3),   # buff holds
            self._bf_snap(4, 2),   # buff expires
            self._bf_snap(5, 2),   # steady state
        ]
        ex = make_executor(snaps)
        card = ex._engine_cards[100]

        results = [
            ex.execute_step(prev, curr) for prev, curr in zip(snaps, snaps[1:])
        ]
        assert [len(self._pt(r)) for r in results] == [1, 0, 1, 0]

        # Printed stats never drift, and the revocable correction is gone.
        assert (card.base_power, card.base_toughness) == (2, 2)
        assert (card.modified_power, card.modified_toughness) == (2, 2)
        assert ex._oracle_pt_corrections() == []

    def test_correction_applies_within_the_same_step(self):
        """The timing trap: apply_all normally runs only at turn boundaries,
        so the resync must re-apply effects itself — the corrected value
        has to be live immediately after the step that derived it."""
        snaps = [self._bf_snap(1, 2), self._bf_snap(2, 3)]
        ex = make_executor(snaps)
        card = ex._engine_cards[100]

        ex.execute_step(snaps[0], snaps[1])
        assert card.power == 3
        assert card.base_power == 2
        assert len(ex._oracle_pt_corrections()) == 1

    def test_correction_survives_turn_boundary_cleanup(self):
        """cleanup_mechanical's remove_expired + apply_all reset must not
        revert a standing correction: the next comparison stays clean."""
        snaps = [
            self._bf_snap(1, 2, turn=1),
            self._bf_snap(2, 3, turn=1),   # missed static buff -> correction
            self._bf_snap(3, 3, turn=2),   # turn boundary: cleanup + untap
        ]
        ex = make_executor(snaps)

        first = ex.execute_step(snaps[0], snaps[1])
        assert len(self._pt(first)) == 1
        second = ex.execute_step(snaps[1], snaps[2])
        assert self._pt(second) == []
        assert ex._engine_cards[100].base_power == 2

    def test_departed_creature_leaves_no_orphaned_correction(self):
        snaps = [
            self._bf_snap(1, 2),
            self._bf_snap(2, 3),                 # correction registered
            self._bf_snap(3, 0, present=False),  # creature leaves the battlefield
        ]
        ex = make_executor(snaps)
        card = ex._engine_cards[100]

        ex.execute_step(snaps[0], snaps[1])
        assert len(ex._oracle_pt_corrections()) == 1
        ex.execute_step(snaps[1], snaps[2])
        assert ex._oracle_pt_corrections() == []
        assert card.base_power == 2


class TestStrictLoader:
    def test_full_fdn_set_loads_with_zero_failures(self):
        """Every FDN card impl imports and instantiates (strict raises on
        any failure — a swallowed loader warning becomes a test failure)."""
        from cards.loader import load_set_registry

        registry = load_set_registry("fdn", strict=True)
        assert len(registry.list_all()) == 284


class TestGoldenGame:
    """Full simulate pipeline over a committed corpus game, fingerprint-pinned.

    The fingerprint is intentionally exact: any executor or engine change
    that shifts this game's divergences must be looked at (and this pin
    updated deliberately), rather than drowning in corpus-level totals.
    """

    FIXTURE = REPO_ROOT / "data" / "replays" / "golden" / "fdn_match0_game0.json"

    def test_divergence_fingerprint(self):
        from collections import Counter

        from cards.loader import load_set_registry
        from silverquillm.replay.parser import load_card_id_map, parse_replay
        from silverquillm.replay.validation import ValidatingExecutor

        card_id_map = load_card_id_map()
        registry = load_set_registry("fdn")
        game = parse_replay(self.FIXTURE, card_id_map=card_id_map)
        executor = ReplayExecutor(
            replay=game, card_id_map=card_id_map, registry=registry, simulate=True
        )
        validator = ValidatingExecutor(executor, card_id_map)
        validator.execute_all()
        report = validator.report()

        by_type = Counter(d.divergence_type.value for d in report.divergences)
        by_category = Counter(
            d.description.split("]")[0].lstrip("[")
            if d.description.startswith("[")
            else d.divergence_type.value
            for d in report.divergences
        )
        # MISSING_CARD is one divergence per (game, identity): the game's
        # six Hare Apparent occurrences dedupe to one, and the unmapped
        # token arrival grpId_94160 — invisible before the battlefield-
        # arrival source landed — is the second. successful_comparisons
        # rose 106 -> 108: the steps carrying Hare Apparent repeats no
        # longer fail on an already-recorded identity.
        assert report.total_snapshots == 116
        assert report.successful_comparisons == 108
        assert dict(by_type) == {"MISSING_CARD": 2, "STATE_MISMATCH": 10}
        assert dict(by_category) == {
            "MISSING_CARD": 2,
            "zone_contents": 8,
            "life_total": 1,
            "tapped_state": 1,
        }
