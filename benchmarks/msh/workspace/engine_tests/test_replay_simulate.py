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


class TestStepAbortGuard:
    """A card crash during ability resolution is a per-action failure —
    the step's remaining actions, comparisons, and resync still run.
    Protocol exceptions keep surfacing per the engine's contract."""

    def _make(self, excs):
        """Executor with one battlefield creature per exception in *excs*,
        each with a pending stack object whose on_resolve raises it, and an
        ability_resolution action per creature. GRE life drops 20 -> 15 at
        the acting snapshot so a completed comparison is observable."""
        from engine.stack import StackObject

        iids = [100 + i for i in range(len(excs))]
        grps = [555100 + i for i in range(len(excs))]

        def bf(gsid: int, life: int = 20) -> GameSnapshot:
            objects = {
                iid: card_obj(iid, grp, 1, BF1,
                              card_types=["CardType_Creature"], power=2, toughness=2)
                for iid, grp in zip(iids, grps)
            }
            snap = snapshot(gsid, battlefield={1: list(iids)}, objects=objects)
            snap.players[1].life_total = life
            return snap

        s0, s1, s2 = bf(1), bf(2, life=15), bf(3, life=15)
        s1.actions = [
            ReplayAction(
                action_type="ability_resolution", turn_number=1, active_player=1,
                player_seat_id=1, card_name=f"src{i}", grp_id=grp,
                instance_id=500 + i,
            )
            for i, grp in enumerate(grps)
        ]
        ex = make_executor([s0, s1, s2])
        for iid, exc in zip(iids, excs):
            card = ex._engine_cards[iid]

            def boom(_game, exc=exc):
                raise exc

            ex.game.stack.push(
                StackObject(source=card, controller=ex.players[1], on_resolve=boom)
            )
        return ex, s0, s1, s2

    def test_card_crash_is_per_action_failure_not_step_abort(self):
        ex, s0, s1, s2 = self._make(
            [RuntimeError("card bug A"), RuntimeError("card bug B")]
        )
        result = ex.execute_step(s0, s1)

        # One ENGINE_ERROR record per failing action; the step completed.
        assert len(result.engine_failures) == 2
        assert all("RuntimeError" in f for f in result.engine_failures)
        # The step's comparisons still ran (GRE life change was observed).
        assert any(m.category == "life_total" for m in result.mismatches)
        # Subsequent steps are unaffected (resync ran).
        follow_up = ex.execute_step(s1, s2)
        assert follow_up.engine_failures == []
        assert follow_up.mismatches == []

    def test_protocol_error_still_surfaces(self):
        from engine.decisions import ProtocolError

        ex, s0, s1, _ = self._make([ProtocolError("boundary failure")])
        with pytest.raises(ProtocolError):
            ex.execute_step(s0, s1)

    def test_unmatched_query_error_still_surfaces(self):
        from engine.decisions import UnmatchedQueryError

        ex, s0, s1, _ = self._make([UnmatchedQueryError("no intent matched")])
        with pytest.raises(UnmatchedQueryError):
            ex.execute_step(s0, s1)


# ---------------------------------------------------------------------------
# Guard-lifecycle tests
#
# Each of the five card-code surfaces the simulate executor drives is guarded
# so a non-protocol crash becomes an ENGINE_ERROR record instead of aborting
# the step. But recording the error is not the whole story — the invariant is
# that a transition is *measured only from fully restored GRE truth*. So every
# test below also proves what happens to the NEXT transition: it is either
# based on fully restored state (the resync healed the crash) or explicitly
# suppressed as unmeasurable (the resync could not, so no comparison is
# emitted from dirty state). Protocol exceptions from every surface propagate.
# ---------------------------------------------------------------------------


def _add_broken_effect(ex, exc, counter):
    """Register a continuous effect whose ``apply`` counts its calls and then
    raises *exc*, so the next ``apply_all`` (resync P/T re-derivation or
    turn-boundary cleanup) crashes. The counter proves the failing path is not
    re-triggered once the effect layer is latched broken."""
    from engine.continuous_effects import (
        DURATION_PERMANENT,
        ContinuousEffect,
        Layer,
        SubLayer,
    )

    class _BrokenSource:
        name = "BrokenEffectSource"

    def _apply(_game):
        counter[0] += 1
        raise exc

    ex.game.effect_manager.add(ContinuousEffect(
        source=_BrokenSource(),
        layer=Layer.POWER_TOUGHNESS,
        sublayer=SubLayer.MODIFY_PT,
        duration=DURATION_PERMANENT,
        apply=_apply,
    ))


class TestResyncTriggerRegistrationGuard:
    """Surface 4: register_triggers on an oracle-injected battlefield permanent.

    A crash there is guarded per card, so the zone sync still completes: the
    compared surfaces (contents, tapped, P/T) are fully restored and only the
    card's own triggers go unregistered. The next transition is therefore
    measured from fully restored state, not suppressed.
    """

    CREATURE = 557000  # unmapped grpId -> Creature shell

    def _bf(self, gsid, *, present=True):
        if not present:
            return snapshot(gsid, battlefield={1: []})
        obj = card_obj(
            101, self.CREATURE, 1, BF1,
            card_types=["CardType_Creature"], power=2, toughness=2,
        )
        return snapshot(gsid, battlefield={1: [101]}, objects={101: obj})

    def _arm(self, ex, exc):
        """Make the creature injected during resync crash in register_triggers."""
        orig = ex._create_card_from_object

        def patched(obj, owner):
            card = orig(obj, owner)
            if getattr(obj, "grp_id", 0) == self.CREATURE:
                def boom(_game):
                    raise exc
                card.register_triggers = boom
            return card

        ex._create_card_from_object = patched

    def test_registration_crash_leaves_next_step_fully_restored(self):
        snaps = [self._bf(1, present=False), self._bf(2), self._bf(3)]
        ex = make_executor(snaps)
        self._arm(ex, RuntimeError("register_triggers boom"))

        # Step 1: the creature first appears; the resync injects it and its
        # register_triggers crashes — recorded, but the resync still completes.
        first = ex.execute_step(snaps[0], snaps[1])
        assert any("register_triggers" in f for f in first.engine_failures)
        assert ex._synced is True  # zones/life/tapped/P/T fully restored
        assert ex._engine_cards.get(101) is not None  # creature is now tracked

        # Step 2: measured from fully restored state — a clean comparison, and
        # register_triggers is NOT re-run (the card is already injected).
        second = ex.execute_step(snaps[1], snaps[2])
        assert second.engine_failures == []
        assert second.mismatches == []
        assert ex._synced is True

    def test_registration_protocol_error_propagates(self):
        from engine.decisions import ProtocolError

        snaps = [self._bf(1, present=False), self._bf(2)]
        ex = make_executor(snaps)
        self._arm(ex, ProtocolError("boundary failure in register_triggers"))
        with pytest.raises(ProtocolError):
            ex.execute_step(snaps[0], snaps[1])


class TestResyncEffectReapplicationGuard:
    """Surface 5: apply_all under the resync's P/T re-derivation.

    A crashing card effect breaks the whole effect layer, so P/T cannot be
    corrected — that is the one resync surface that leaves a compared value
    dirty. The executor is marked dirty and every following transition is
    suppressed as unmeasurable, and the recovery barrier never re-triggers the
    crashing apply_all (proved by the call counter staying at 1).
    """

    CREATURE = 556000  # unmapped grpId -> Creature shell

    def _bf(self, gsid, power, *, turn=1):
        obj = card_obj(
            100, self.CREATURE, 1, BF1,
            card_types=["CardType_Creature"], power=power, toughness=2,
        )
        return snapshot(gsid, turn=turn, battlefield={1: [100]}, objects={100: obj})

    def test_apply_all_crash_dirties_and_suppresses_following_transitions(self):
        # GRE shows a +1/+0 the engine missed from snap2 on, so the resync has
        # a delta to correct and calls apply_all — which crashes.
        snaps = [self._bf(1, 2), self._bf(2, 3), self._bf(3, 3), self._bf(4, 3)]
        ex = make_executor(snaps)
        counter = [0]
        _add_broken_effect(ex, RuntimeError("effect apply boom"), counter)

        # Step 1 started from clean state, so it is measured: the missed buff
        # is a genuine P/T mismatch. The end-of-step resync then crashes in
        # apply_all, latching the effect layer broken and marking dirty.
        first = ex.execute_step(snaps[0], snaps[1])
        assert any(m.category == "power_toughness" for m in first.mismatches)
        assert any("apply_all" in f for f in first.engine_failures)
        assert ex._effects_broken is True
        assert ex._synced is False
        assert counter[0] == 1

        # Step 2: enters dirty. Recovery to the previous snapshot cannot
        # complete (apply_all is skipped, not re-run), so the transition is
        # suppressed — no comparison emitted from dirty state.
        second = ex.execute_step(snaps[1], snaps[2])
        assert second.skipped is True
        assert second.mismatches == []
        assert any("unmeasurable" in f for f in second.infra_failures)
        assert second.engine_failures == []
        assert counter[0] == 1  # apply_all NOT re-triggered

        # Step 3: repeated recovery failure — still suppressed, still no
        # re-trigger of the failing card-code path.
        third = ex.execute_step(snaps[2], snaps[3])
        assert third.skipped is True
        assert third.mismatches == []
        assert any("unmeasurable" in f for f in third.infra_failures)
        assert counter[0] == 1

    def test_apply_all_protocol_error_propagates(self):
        from engine.decisions import ProtocolError

        snaps = [self._bf(1, 2), self._bf(2, 3)]
        ex = make_executor(snaps)
        _add_broken_effect(ex, ProtocolError("boundary failure in apply_all"), [0])
        with pytest.raises(ProtocolError):
            ex.execute_step(snaps[0], snaps[1])


class TestTurnBoundaryCleanupSplit:
    """Surface 3: turn-boundary cleanup vs untap, independently guarded.

    cleanup_mechanical leads with apply_all (card code); untap is pure engine
    bookkeeping. A cleanup crash must not cost us the untap, and it marks the
    executor dirty so the next transition is suppressed rather than measured
    from a half-cleaned state.
    """

    CREATURE = 558000  # unmapped grpId -> Creature shell

    def _bf(self, gsid, *, turn):
        obj = card_obj(
            102, self.CREATURE, 1, BF1,
            card_types=["CardType_Creature"], power=2, toughness=2,
        )
        return snapshot(
            gsid, turn=turn, active=1,
            battlefield={1: [102]}, objects={102: obj},
        )

    def test_cleanup_failure_does_not_skip_untap(self):
        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)
        card = ex._engine_cards[102]
        card.is_tapped = True
        card.summoning_sick = True
        ex.players[1].land_plays_remaining = 0
        _add_broken_effect(ex, RuntimeError("cleanup apply boom"), [0])

        result = StepResult(snapshot_id=2)
        prev_turn = TurnInfo(
            phase="Phase_Ending", step="Step_End", turn_number=1, active_player=1
        )
        curr_turn = TurnInfo(
            phase="Phase_Beginning", step="Step_Upkeep", turn_number=2, active_player=1
        )
        ex._handle_turn_info(prev_turn, curr_turn, result)

        # Cleanup crashed and was recorded, and the executor is marked dirty.
        assert any("turn-boundary cleanup" in f for f in result.engine_failures)
        assert ex._effects_broken is True
        assert ex._synced is False
        # ...but untap still ran: tapped/summoning-sickness/land-plays advanced.
        assert card.is_tapped is False
        assert card.summoning_sick is False
        assert ex.players[1].land_plays_remaining == 1

    def test_cleanup_failure_suppresses_the_next_transition(self):
        snaps = [
            self._bf(1, turn=1),
            self._bf(2, turn=1),  # end of turn 1
            self._bf(3, turn=2),  # turn boundary here: cleanup runs and crashes
            self._bf(4, turn=2),
        ]
        ex = make_executor(snaps)
        counter = [0]
        _add_broken_effect(ex, RuntimeError("cleanup apply boom"), counter)

        ex.execute_step(snaps[0], snaps[1])  # within turn 1, no cleanup
        boundary = ex.execute_step(snaps[1], snaps[2])  # turn boundary
        assert any("turn-boundary cleanup" in f for f in boundary.engine_failures)
        assert ex._effects_broken is True
        assert counter[0] == 1

        # The transition after the cleanup crash is suppressed, not measured.
        following = ex.execute_step(snaps[2], snaps[3])
        assert following.skipped is True
        assert following.mismatches == []
        assert any("unmeasurable" in f for f in following.infra_failures)
        assert counter[0] == 1  # cleanup's apply_all not re-triggered

    def test_cleanup_protocol_error_propagates(self):
        from engine.decisions import ProtocolError

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)
        _add_broken_effect(ex, ProtocolError("boundary failure in cleanup"), [0])
        result = StepResult(snapshot_id=2)
        prev_turn = TurnInfo(
            phase="Phase_Ending", step="Step_End", turn_number=1, active_player=1
        )
        curr_turn = TurnInfo(
            phase="Phase_Beginning", step="Step_Upkeep", turn_number=2, active_player=1
        )
        with pytest.raises(ProtocolError):
            ex._handle_turn_info(prev_turn, curr_turn, result)


class TestTurnBoundaryUntapRecovery:
    """Non-protocol untap failures and the operational-state domain.

    ``untap_step`` is pure engine bookkeeping (untap the active player's
    permanents, clear summoning sickness, reset land plays), but a broken
    implementation can partially mutate state and then raise. Those three
    surfaces — summoning sickness and land plays especially — are NOT read by
    compare_state, so the post-step P/T resync (which sets ``_synced`` True)
    would happily overwrite a bare dirty marker and let a later transition
    execute from half-untapped state.

    The fix tracks operational dirtiness in its own domain (``_operational_dirty``)
    that the resync never touches, and repairs untap DETERMINISTICALLY: the
    failing entry point is not retried; the three invariants are re-done with
    idempotent attribute writes. If even that cannot complete, the domain
    latches dirty and every later transition is suppressed as unmeasurable
    until the next successful turn-boundary untap.
    """

    CREATURE = 559000  # unmapped grpId -> Creature shell

    def _bf(self, gsid, *, turn):
        obj = card_obj(
            103, self.CREATURE, 1, BF1,
            card_types=["CardType_Creature"], power=2, toughness=2,
        )
        return snapshot(
            gsid, turn=turn, active=1,
            battlefield={1: [103]}, objects={103: obj},
        )

    @staticmethod
    def _partial_then_raise(exc, did):
        """A broken ``untap_step``: untap ``is_tapped`` on the active player's
        permanents (partial mutation) and then raise before summoning sickness
        and land plays are restored. ``did`` counts invocations, proving the
        failing operation is executed exactly once — never retried."""
        def broken(game):
            from engine.types import Zone
            did[0] += 1
            active = game.active_player
            for card in active.zones[Zone.BATTLEFIELD].get_all():
                if hasattr(card, "is_tapped"):
                    card.is_tapped = False
            raise exc
        return broken

    _PREV_TURN = TurnInfo(
        phase="Phase_Ending", step="Step_End", turn_number=1, active_player=1
    )
    _CURR_TURN = TurnInfo(
        phase="Phase_Beginning", step="Step_Upkeep", turn_number=2, active_player=1
    )

    def test_untap_failure_records_one_error_and_deterministically_repairs(
        self, monkeypatch
    ):
        # The current step began from clean state, so the untap crash is
        # honestly attributable here: exactly one ENGINE_ERROR, and the
        # deterministic fallback restores every untap invariant in place.
        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)
        card = ex._engine_cards[103]
        card.is_tapped = True
        card.summoning_sick = True
        ex.players[1].land_plays_remaining = 0

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(RuntimeError("untap boom"), did),
        )

        result = StepResult(snapshot_id=2)
        ex._handle_turn_info(self._PREV_TURN, self._CURR_TURN, result)

        # Exactly one current-step ENGINE_ERROR — the untap crash, not the
        # fallback (which records nothing on success).
        assert len(result.engine_failures) == 1
        assert "turn-boundary untap" in result.engine_failures[0]
        assert not any("untap fallback" in f for f in result.engine_failures)
        assert did[0] == 1  # the failing untap_step ran exactly once

        # Deterministic repair restored ALL untap invariants...
        assert card.is_tapped is False
        assert card.summoning_sick is False
        assert ex.players[1].land_plays_remaining == 1
        # ...so the operational domain is clean and nothing is latched.
        assert ex._operational_dirty is False
        assert ex._fully_synced is True

    def test_pt_resync_success_cannot_clear_operational_dirty(self):
        # The direct domain-separation invariant: success in the compared/P/T
        # domain must never promote an operationally-dirty executor to fully
        # synchronized.
        snaps = [self._bf(1, turn=1), self._bf(2, turn=1)]
        ex = make_executor(snaps)
        ex._operational_dirty = True

        # A full P/T resync restores the compared surfaces and sets _synced.
        assert ex._resync_to_snapshot(snaps[1]) is True
        assert ex._synced is True
        # But the operational domain is independent — the resync never touches
        # it — so the executor is NOT fully synchronized.
        assert ex._operational_dirty is True
        assert ex._fully_synced is False

    def test_deterministic_repair_lets_following_transition_measure_cleanly(
        self, monkeypatch
    ):
        # Full lifecycle, preferred path: the untap crash is repaired in place,
        # so the FOLLOWING transition is measured from fully restored state
        # (not suppressed) and shows no residue mismatch from the partial untap.
        snaps = [
            self._bf(1, turn=1),
            self._bf(2, turn=1),   # within turn 1
            self._bf(3, turn=2),   # turn boundary: untap crashes, fallback repairs
            self._bf(4, turn=2),
        ]
        ex = make_executor(snaps)
        ex.execute_step(snaps[0], snaps[1])

        card = ex._engine_cards[103]
        card.summoning_sick = True
        ex.players[1].land_plays_remaining = 0
        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(RuntimeError("untap boom"), did),
        )

        boundary = ex.execute_step(snaps[1], snaps[2])
        assert any("turn-boundary untap" in f for f in boundary.engine_failures)
        # Fallback repaired the operational invariants...
        assert card.summoning_sick is False
        assert ex.players[1].land_plays_remaining == 1
        assert ex._operational_dirty is False

        # ...so the following transition is measured, not suppressed, and clean.
        following = ex.execute_step(snaps[2], snaps[3])
        assert following.skipped is False
        assert following.mismatches == []
        assert did[0] == 1  # untap_step not re-run

    def test_unrecoverable_untap_suppresses_following_transitions(self, monkeypatch):
        # Full lifecycle, fail-closed path: when even the deterministic fallback
        # cannot complete, the operational domain latches dirty and every later
        # transition is suppressed — no comparison emitted from dirty state, and
        # neither the failing untap nor the fallback is re-run during recovery.
        snaps = [
            self._bf(1, turn=1),
            self._bf(2, turn=1),   # within turn 1
            self._bf(3, turn=2),   # turn boundary: untap crashes, fallback fails
            self._bf(4, turn=2),
            self._bf(5, turn=2),
        ]
        ex = make_executor(snaps)

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(RuntimeError("untap boom"), did),
        )
        fallback_calls = [0]

        def _failing_fallback(result=None):
            fallback_calls[0] += 1
            ex._record_engine_failure(result, "untap fallback: RuntimeError: no repair")
            return False

        monkeypatch.setattr(ex, "_fallback_untap", _failing_fallback)

        ex.execute_step(snaps[0], snaps[1])  # within turn 1, no boundary
        boundary = ex.execute_step(snaps[1], snaps[2])  # boundary: untap fails
        # The boundary step started clean, so it is still measured and records
        # the ENGINE_ERROR; the operational domain is now latched dirty.
        assert any("turn-boundary untap" in f for f in boundary.engine_failures)
        assert boundary.skipped is False
        assert ex._operational_dirty is True
        assert did[0] == 1
        assert fallback_calls[0] == 1

        # The next transition is suppressed as unmeasurable — no mismatch from
        # the partially untapped state.
        following = ex.execute_step(snaps[2], snaps[3])
        assert following.skipped is True
        assert following.mismatches == []
        assert any("unmeasurable" in f for f in following.infra_failures)
        # Recovery re-ran neither the failing untap nor the fallback.
        assert did[0] == 1
        assert fallback_calls[0] == 1

        # Still suppressed a step later — the latch persists within the turn.
        third = ex.execute_step(snaps[3], snaps[4])
        assert third.skipped is True
        assert third.mismatches == []
        assert did[0] == 1
        assert fallback_calls[0] == 1

    def test_fallback_untap_records_error_and_returns_false_on_write_failure(self):
        # The real fallback's fail-closed branch: a non-protocol error during
        # its idempotent writes is recorded and reported False (so the caller
        # latches operational dirtiness).
        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)
        from engine.types import Zone

        def _boom():
            raise RuntimeError("zone read boom")

        ex.game.active_player.zones[Zone.BATTLEFIELD].get_all = _boom
        result = StepResult(snapshot_id=1)
        assert ex._fallback_untap(result) is False
        assert any("untap fallback: RuntimeError" in f for f in result.engine_failures)

    def test_untap_protocol_error_propagates(self, monkeypatch):
        from engine.decisions import ProtocolError

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)

        def boom(game):
            raise ProtocolError("boundary failure in untap")

        monkeypatch.setattr("engine.turn.untap_step", boom)
        with pytest.raises(ProtocolError):
            ex._handle_turn_info(self._PREV_TURN, self._CURR_TURN, StepResult(snapshot_id=2))

    def test_untap_unmatched_query_error_propagates(self, monkeypatch):
        from engine.decisions import UnmatchedQueryError

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)

        def boom(game):
            raise UnmatchedQueryError("no intent matched during untap")

        monkeypatch.setattr("engine.turn.untap_step", boom)
        with pytest.raises(UnmatchedQueryError):
            ex._handle_turn_info(self._PREV_TURN, self._CURR_TURN, StepResult(snapshot_id=2))

    def test_fallback_untap_protocol_error_propagates(self):
        from engine.decisions import ProtocolError
        from engine.types import Zone

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)

        def _boom():
            raise ProtocolError("boundary failure in fallback")

        ex.game.active_player.zones[Zone.BATTLEFIELD].get_all = _boom
        with pytest.raises(ProtocolError):
            ex._fallback_untap(StepResult(snapshot_id=1))


class TestStackExitResolutionGuard:
    """Surface 1: stack-exit on_resolve in _simulate_zone_transition.

    A card crash resolving one stack object is a per-action failure: the
    step's remaining actions still run, and the resync heals the state so the
    next transition is measured from restored truth.
    """

    def _spell_card(self, ex, iid, name):
        from engine.card import CardImpl

        card = CardImpl(name=name, owner=ex.players[1], controller=ex.players[1])
        ex._engine_cards[iid] = card
        return card

    def _zone_exit(self, iid, name):
        return ReplayAction(
            action_type="zone_transition", turn_number=1, active_player=1,
            player_seat_id=1, card_name=name, instance_id=iid,
            source_zone="ZoneType_Stack", dest_zone="ZoneType_Graveyard",
        )

    def test_resolution_crash_lets_later_action_run_and_next_step_is_clean(self):
        from engine.stack import StackObject

        s0, s1, s2 = snapshot(1), snapshot(2), snapshot(3)
        s1.actions = [self._zone_exit(200, "A"), self._zone_exit(210, "B")]
        ex = make_executor([s0, s1, s2])
        card_a = self._spell_card(ex, 200, "A")
        card_b = self._spell_card(ex, 210, "B")
        ran = []

        def boom_a(_game):
            raise RuntimeError("resolve A boom")

        def resolve_b(_game):
            ran.append("B")

        ex.game.stack.push(StackObject(
            source=card_a, controller=ex.players[1], on_resolve=boom_a))
        ex.game.stack.push(StackObject(
            source=card_b, controller=ex.players[1], on_resolve=resolve_b))

        first = ex.execute_step(s0, s1)
        # A's stack exit crashed -> exactly one ENGINE_ERROR for it.
        stack_exit_fails = [f for f in first.engine_failures if "stack exit" in f]
        assert len(stack_exit_fails) == 1
        assert "A" in stack_exit_fails[0]
        # B still resolved despite A's crash (the later action ran).
        assert ran == ["B"]
        assert ex.game.stack.is_empty()
        assert ex._synced is True

        # The following transition is measured from restored state.
        second = ex.execute_step(s1, s2)
        assert second.engine_failures == []
        assert second.mismatches == []

    def test_resolution_protocol_error_propagates(self):
        from engine.decisions import ProtocolError
        from engine.stack import StackObject

        s0, s1 = snapshot(1), snapshot(2)
        s1.actions = [self._zone_exit(200, "A")]
        ex = make_executor([s0, s1])
        card_a = self._spell_card(ex, 200, "A")

        def boom_protocol(_game):
            raise ProtocolError("boundary failure resolving A")

        ex.game.stack.push(StackObject(
            source=card_a, controller=ex.players[1], on_resolve=boom_protocol))
        with pytest.raises(ProtocolError):
            ex.execute_step(s0, s1)


class TestDrawTriggerGuard:
    """Surface 2: a draw trigger that crashes after the library-to-hand move.

    draw_card mutates zones first, then fires the draw event, so a crashing
    draw trigger is caught after the card has already reached the hand. The
    step still completes and the resync heals the drawn card's identity, so
    the next transition is measured from restored state.
    """

    def _draw_snaps(self):
        # seat 1 draws: library id 102 re-minted as hand id 130 (id_change),
        # both hand cards carry real (registered) identities so the seat-1
        # hand comparison is meaningful rather than hidden-shell noise.
        h101 = card_obj(101, FOREST, 1, HAND1)
        h130 = card_obj(130, ISLAND, 1, HAND1)
        s0 = snapshot(1, hands={1: [101]}, libraries={1: [102, 103]},
                      objects={101: h101})
        s1 = snapshot(
            2, hands={1: [101, 130]}, libraries={1: [103]},
            objects={101: h101, 130: h130}, annotations=[id_change(911, 102, 130)],
        )
        s2 = snapshot(3, hands={1: [101, 130]}, libraries={1: [103]},
                      objects={101: h101, 130: h130})
        return s0, s1, s2

    def _register_draw_trigger(self, ex, exc):
        from engine.events import DrawsCardTriggeredEvent
        from engine.triggers import TriggerRegistration

        class _Src:
            name = "DrawWatcher"

        def boom_condition(_game, _event):
            raise exc

        ex.game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=boom_condition,
            effect=lambda _game: None,
            source=_Src(),
            controller=ex.players[1],
        ))

    def test_draw_trigger_crash_after_mutation_then_restored(self):
        from engine.types import Zone as EZone

        s0, s1, s2 = self._draw_snaps()
        ex = make_executor([s0, s1, s2])
        self._register_draw_trigger(ex, RuntimeError("draw trigger boom"))
        hand_before = len(ex.players[1].zones[EZone.HAND].get_all())
        lib_before = len(ex.players[1].zones[EZone.LIBRARY].get_all())

        first = ex.execute_step(s0, s1)
        # The draw trigger crashed and was recorded...
        assert any("draw_card" in f for f in first.engine_failures)
        # ...but the library-to-hand mutation already happened.
        assert len(ex.players[1].zones[EZone.HAND].get_all()) == hand_before + 1
        assert len(ex.players[1].zones[EZone.LIBRARY].get_all()) == lib_before - 1
        assert ex._synced is True  # resync healed the drawn card's identity

        # The following transition is measured from restored state.
        second = ex.execute_step(s1, s2)
        assert second.engine_failures == []
        assert second.mismatches == []

    def test_draw_trigger_protocol_error_propagates(self):
        from engine.decisions import ProtocolError

        s0, s1, _ = self._draw_snaps()
        ex = make_executor([s0, s1])
        self._register_draw_trigger(ex, ProtocolError("boundary failure in draw"))
        with pytest.raises(ProtocolError):
            ex.execute_step(s0, s1)


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
