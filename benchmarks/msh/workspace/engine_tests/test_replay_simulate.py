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


class _CounterPerm:
    """Minimal engine permanent stand-in carrying the counter fields the
    reconcile writes (used to exercise refs-based stint retirement)."""

    def __init__(self, oid: int) -> None:
        self.object_id = oid
        self.name = "Counter Perm"
        self.plus_one_counters = 0
        self._base_plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_minus_one_counters = 0
        self._generic_counters: dict = {}


def _counter_added(ann_id: int, aid: int, amount: int) -> Annotation:
    return Annotation(
        id=ann_id, affector_id=0, affected_ids=[aid],
        type=["AnnotationType_CounterAdded"],
        details={"counter_type": [1], "transaction_amount": [amount]},
    )


class TestCounterStintRetirement:
    """Counter reconciliation is anchored to the engine object and retires when
    that object leaves the engine battlefield (a real zone transition). Run
    against the real simulate-mode engine game (its own players/zones)."""

    def _executor(self):
        return make_executor([snapshot(1)])

    def test_blink_off_battlefield_retires_counter(self):
        from engine.types import Zone as EZone

        ex = self._executor()
        perm = _CounterPerm(90001)
        ex.players[1].zones[EZone.BATTLEFIELD].add(perm)
        ex._engine_cards[6501] = perm

        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [6501]}, objects={6501: card_obj(6501, 0, 1, BF1)},
            annotations=[_counter_added(26, 6501, 3)],
        ))
        assert perm.plus_one_counters == 3
        assert perm._base_plus_one_counters == 3

        # Blink: perm leaves the engine battlefield -> its counters are retired.
        ex.players[1].zones[EZone.BATTLEFIELD].remove(perm)
        ex._apply_counter_annotations(snapshot(3))  # no annotation
        assert perm.plus_one_counters == 0
        assert perm._base_plus_one_counters == 0

    def test_no_zone_change_preserves_counter_across_gre_churn(self):
        from engine.types import Zone as EZone

        ex = self._executor()
        perm = _CounterPerm(90002)
        ex.players[1].zones[EZone.BATTLEFIELD].add(perm)
        ex._engine_cards[6601] = perm

        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [6601]}, objects={6601: card_obj(6601, 0, 1, BF1)},
            annotations=[_counter_added(28, 6601, 3)],
        ))
        assert perm.plus_one_counters == 3
        # No zone change: the object stays on the engine battlefield, so the
        # counter is preserved even across snapshots that fold nothing and across
        # GRE id churn (the aid is irrelevant to the engine-object-keyed ledger).
        ex._engine_cards[6602] = perm  # GRE re-mints the aid; same engine object
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [6602]}, objects={6602: card_obj(6602, 0, 1, BF1)},
        ))
        assert perm.plus_one_counters == 3


def _named_counter(ann_id: int, aid: int, ctype: int, amount: int) -> Annotation:
    return Annotation(
        id=ann_id, affector_id=0, affected_ids=[aid],
        type=["AnnotationType_CounterAdded"],
        details={"counter_type": [ctype], "transaction_amount": [amount]},
    )


class TestCounterLifecycleIntegration:
    """Full counter-lifecycle integration: real engine creatures moved through
    the REAL ``move_to_zone`` (which advances ``refs.zone_epoch``), so a
    battlefield -> X -> battlefield round trip completed ENTIRELY between two
    ``_apply_counter_annotations`` calls is a real zone transition the ledger
    must observe — no manually inserted sampling point ever sees the object
    off the battlefield."""

    def _executor(self):
        return make_executor([snapshot(1)])

    def _creature(self, ex, seat: int = 1, name: str = "Test Bear", grp: int = 0):
        from engine.card import Creature
        from engine.types import Zone as EZone

        player = ex.players[seat]
        card = Creature(
            name=name, owner=player, controller=player,
            base_power=2, base_toughness=2,
        )
        if grp:
            card._grp_id = grp
        player.zones[EZone.BATTLEFIELD].add(card)
        return card

    def _blink(self, ex, card, via: str = "exile") -> None:
        """battlefield -> via -> battlefield through the real engine mover."""
        from engine.types import Zone as EZone
        from engine.zones import move_to_zone

        mid = EZone.EXILE if via == "exile" else EZone.GRAVEYARD
        move_to_zone(ex.game, card, EZone.BATTLEFIELD, mid)
        move_to_zone(ex.game, card, mid, EZone.BATTLEFIELD)

    # -- required tests 1-3: atomic round trips retire the ledger -----------

    def test_atomic_exile_round_trip_clears_counter(self):
        ex = self._executor()
        card = self._creature(ex)
        ex._engine_cards[7001] = card
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7001]}, objects={7001: card_obj(7001, 0, 1, BF1)},
            annotations=[_counter_added(40, 7001, 2)],
        ))
        assert card.plus_one_counters == 2
        assert card._base_plus_one_counters == 2

        # The blink happens ENTIRELY between the two reconciliations: at the
        # next call the object is back on the engine battlefield, so
        # membership alone cannot see the transition — the zone epoch does.
        self._blink(ex, card, via="exile")
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7002]}, objects={7002: card_obj(7002, 0, 1, BF1)},
        ))
        assert card.plus_one_counters == 0
        assert card._base_plus_one_counters == 0

    def test_atomic_graveyard_round_trip_clears_counter(self):
        ex = self._executor()
        card = self._creature(ex)
        ex._engine_cards[7101] = card
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7101]}, objects={7101: card_obj(7101, 0, 1, BF1)},
            annotations=[_counter_added(41, 7101, 3)],
        ))
        assert card.plus_one_counters == 3

        self._blink(ex, card, via="graveyard")  # died and was reanimated
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7102]}, objects={7102: card_obj(7102, 0, 1, BF1)},
        ))
        assert card.plus_one_counters == 0
        assert card._base_plus_one_counters == 0

    def test_atomic_round_trip_clears_named_generic_counter(self):
        ex = self._executor()
        card = self._creature(ex, name="Drake Hatcher")
        ex._engine_cards[7201] = card
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7201]}, objects={7201: card_obj(7201, 0, 1, BF1)},
            annotations=[_named_counter(42, 7201, 200, 4)],  # incubation x4
        ))
        assert card._generic_counters.get("incubation") == 4

        self._blink(ex, card, via="exile")
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7202]}, objects={7202: card_obj(7202, 0, 1, BF1)},
        ))
        assert card._generic_counters.get("incubation", 0) == 0

    # -- required test 4: no resurrection through unrelated reconciliation --

    def test_unrelated_annotation_after_atomic_blink_does_not_resurrect(self):
        ex = self._executor()
        card = self._creature(ex)
        other = self._creature(ex, name="Bystander")
        ex._engine_cards[7301] = card
        ex._engine_cards[7302] = other
        bf_objs = {7301: card_obj(7301, 0, 1, BF1), 7302: card_obj(7302, 0, 1, BF1)}
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7301, 7302]}, objects=dict(bf_objs),
            annotations=[_counter_added(43, 7301, 2)],
        ))
        assert card.plus_one_counters == 2

        self._blink(ex, card, via="exile")
        # An unrelated permanent's counter drives a reconcile pass — the
        # blinked object's retired ledger must not be re-written by it.
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7303, 7302]},
            objects={7303: card_obj(7303, 0, 1, BF1), 7302: bf_objs[7302]},
            annotations=[_counter_added(44, 7302, 1)],
        ))
        assert other.plus_one_counters == 1
        assert card.plus_one_counters == 0
        assert card._base_plus_one_counters == 0

    # -- required test 5: pending effects vs. stale bindings ----------------

    def test_pending_effect_not_applied_through_stale_binding(self):
        from engine.types import Zone as EZone
        from engine.zones import move_to_zone

        ex = self._executor()
        card = self._creature(ex)
        # The CounterAdded arrives while the object is not yet correlated
        # (grp 0 blocks the same-snapshot grpId match) -> deferred.
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7401]}, objects={7401: card_obj(7401, 0, 1, BF1)},
            annotations=[_counter_added(45, 7401, 2)],
        ))
        assert (45, 7401) in ex._pending_counter_effects

        # The target dies before correlation; a stale binding then appears (a
        # resync rebuild may retain object bindings). GRE shows the aid gone.
        move_to_zone(ex.game, card, EZone.BATTLEFIELD, EZone.GRAVEYARD)
        ex._engine_cards[7401] = card  # stale: the object is NOT on the bf
        ex._apply_counter_annotations(snapshot(3))
        assert card.plus_one_counters == 0
        assert (45, 7401) not in ex._pending_counter_effects
        assert (45, 7401) in ex._cancelled_counter_effects
        assert (45, 7401) not in ex._applied_counter_effects
        assert any(
            rec["annotation_id"] == 45 for rec in ex._unresolved_counter_effects
        )

    def test_stale_binding_rejected_even_when_gre_stream_lags(self):
        from engine.types import Zone as EZone
        from engine.zones import move_to_zone

        ex = self._executor()
        card = self._creature(ex)
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7451]}, objects={7451: card_obj(7451, 0, 1, BF1)},
            annotations=[_counter_added(46, 7451, 2)],
        ))
        assert (46, 7451) in ex._pending_counter_effects

        # Engine-side departure with a GRE snapshot that STILL lists the aid
        # on the battlefield (lagging stream): the engine-candidate gate must
        # reject the stale binding — the fold needs a candidate that is on the
        # engine battlefield RIGHT NOW.
        move_to_zone(ex.game, card, EZone.BATTLEFIELD, EZone.GRAVEYARD)
        ex._engine_cards[7451] = card  # stale
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7451]}, objects={7451: card_obj(7451, 0, 1, BF1)},
        ))
        assert card.plus_one_counters == 0
        assert (46, 7451) not in ex._applied_counter_effects
        assert (46, 7451) in ex._pending_counter_effects  # still unproven

    # -- required test 6: deferred effect never lands on a returned stint ---

    def test_deferred_effect_does_not_apply_to_returned_stint(self):
        ex = self._executor()
        card = self._creature(ex)
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7501]}, objects={7501: card_obj(7501, 0, 1, BF1)},
            annotations=[_counter_added(47, 7501, 2)],
        ))
        assert (47, 7501) in ex._pending_counter_effects

        # Blink; GRE mints a NEW aid for the returned stint and the executor
        # correlates it. The old effect belonged to the departed stint.
        self._blink(ex, card, via="exile")
        ex._engine_cards.clear()
        ex._engine_cards[7502] = card  # returned stint, correlated
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7502]}, objects={7502: card_obj(7502, 0, 1, BF1)},
        ))
        assert card.plus_one_counters == 0
        assert (47, 7501) in ex._cancelled_counter_effects
        assert (47, 7501) not in ex._applied_counter_effects

    def test_deferred_effect_not_rekeyed_through_blink_rename_chain(self):
        ex = self._executor()
        card = self._creature(ex)
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7601]}, objects={7601: card_obj(7601, 0, 1, BF1)},
            annotations=[_counter_added(48, 7601, 2)],
        ))
        assert (48, 7601) in ex._pending_counter_effects

        # The blink's two legs surface as an ObjectIdChanged CHAIN in one
        # snapshot (7601 -> 7602 exile leg, 7602 -> 7603 return leg). A chain
        # is a zone transit, not churn: the effect must NOT follow it to the
        # returned stint even though the final id sits on the battlefield.
        self._blink(ex, card, via="exile")
        ex._engine_cards.clear()
        ex._engine_cards[7603] = card
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7603]}, objects={7603: card_obj(7603, 0, 1, BF1)},
            annotations=[id_change(900, 7601, 7602), id_change(901, 7602, 7603)],
        ))
        assert card.plus_one_counters == 0
        assert (48, 7601) in ex._cancelled_counter_effects

    # -- required test 7: graveyard twin must not steal a battlefield match --

    def test_graveyard_gre_object_does_not_match_battlefield_twin(self):
        GRP = 91234
        ex = self._executor()
        bf_twin = self._creature(ex, name="Twin", grp=GRP)  # unclaimed, unique
        grave_obj = GameObject(
            instance_id=7701, grp_id=GRP, type="GameObjectType_Card",
            zone_id=77, owner_seat_id=1, controller_seat_id=1,
        )
        snap = snapshot(2, battlefield={1: []}, objects={7701: grave_obj})
        snap.zones[77] = Zone(
            zone_id=77, type="ZoneType_Graveyard", owner_seat_id=1,
            object_instance_ids=[7701],
        )
        # Direct probe: the matcher refuses a GRE object that is NOT on the
        # GRE battlefield, however unique the same-grpId engine candidate is.
        assert ex._match_new_battlefield_permanent(7701, snap) is None
        # End-to-end: the annotation defers rather than landing on the twin.
        snap.annotations = [_counter_added(49, 7701, 2)]
        ex._apply_counter_annotations(snap)
        assert bf_twin.plus_one_counters == 0
        assert (49, 7701) not in ex._applied_counter_effects

    # -- required test 8: same grpId across players must not cross-bind -----

    def test_same_grpid_across_players_does_not_cross_bind(self):
        GRP = 91235
        ex = self._executor()
        seat1_perm = self._creature(ex, seat=1, name="Shared Card", grp=GRP)
        # GRE: the counter lands on SEAT 2's copy; seat 2 has no unclaimed
        # engine candidate yet -> the effect must stay pending, never bind to
        # seat 1's same-grpId permanent.
        gre_obj = GameObject(
            instance_id=7801, grp_id=GRP, type="GameObjectType_Card",
            zone_id=BF1, owner_seat_id=2, controller_seat_id=2,
        )
        ex._apply_counter_annotations(snapshot(
            2, battlefield={2: [7801]}, objects={7801: gre_obj},
            annotations=[_counter_added(50, 7801, 2)],
        ))
        assert seat1_perm.plus_one_counters == 0
        assert (50, 7801) in ex._pending_counter_effects

        # Seat 2's copy appears in the engine; the retry selects it by the
        # controller constraint.
        seat2_perm = self._creature(ex, seat=2, name="Shared Card", grp=GRP)
        ex._apply_counter_annotations(snapshot(
            3, battlefield={2: [7801]}, objects={7801: gre_obj},
        ))
        assert seat2_perm.plus_one_counters == 2
        assert seat1_perm.plus_one_counters == 0
        assert (50, 7801) in ex._applied_counter_effects

    # -- required test 9: pure churn keeps counters AND pending effects -----

    def test_pending_effect_follows_pure_churn_rename(self):
        ex = self._executor()
        card = self._creature(ex)
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [7901]}, objects={7901: card_obj(7901, 0, 1, BF1)},
            annotations=[_counter_added(51, 7901, 2)],
        ))
        assert (51, 7901) in ex._pending_counter_effects

        # GRE re-mints the id WITHOUT a zone change (single hop, target on the
        # battlefield, identity-consistent). No engine zone move happened. The
        # pending effect re-keys and folds once the engine correlates.
        ex._engine_cards[7902] = card
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [7902]}, objects={7902: card_obj(7902, 0, 1, BF1)},
            annotations=[id_change(902, 7901, 7902)],
        ))
        assert card.plus_one_counters == 2
        assert (51, 7901) in ex._applied_counter_effects

    def test_folded_counter_survives_churn_without_zone_change(self):
        ex = self._executor()
        card = self._creature(ex)
        ex._engine_cards[8001] = card
        ex._apply_counter_annotations(snapshot(
            2, battlefield={1: [8001]}, objects={8001: card_obj(8001, 0, 1, BF1)},
            annotations=[_counter_added(52, 8001, 3)],
        ))
        assert card.plus_one_counters == 3

        # Churn only — the engine object never moved, its epoch is unchanged,
        # so the object-keyed ledger is preserved across the re-mint.
        del ex._engine_cards[8001]
        ex._engine_cards[8002] = card
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [8002]}, objects={8002: card_obj(8002, 0, 1, BF1)},
        ))
        assert card.plus_one_counters == 3

    # -- required test 10: same-snapshot new-permanent correlation lands ----

    def test_same_snapshot_new_permanent_counter_lands_exactly_once(self):
        GRP = 91236
        ex = self._executor()
        newcomer = self._creature(ex, name="Newcomer", grp=GRP)
        gre_obj = GameObject(
            instance_id=8101, grp_id=GRP, type="GameObjectType_Card",
            zone_id=BF1, owner_seat_id=1, controller_seat_id=1,
        )
        snap2 = snapshot(
            2, battlefield={1: [8101]}, objects={8101: gre_obj},
            annotations=[_counter_added(53, 8101, 2)],
        )
        # Not in _engine_cards yet (first appearance): the same-snapshot
        # battlefield grpId match correlates it — controller-checked.
        ex._apply_counter_annotations(snap2)
        assert newcomer.plus_one_counters == 2
        # Persistent-slot repeat: exactly once.
        ex._apply_counter_annotations(snapshot(
            3, battlefield={1: [8101]}, objects={8101: gre_obj},
            annotations=[_counter_added(53, 8101, 2)],
        ))
        assert newcomer.plus_one_counters == 2
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


# Real FDN token-block grpIds (from data/replays/token_id_map.json).
RABBIT_TOK, CAT_TOK = 94160, 94156
DRAGON4_TOK, DRAGON5_TOK = 94171, 94172  # both red Dragons, base 4/4 vs 5/5

# The two runtime-signature COLLISION sets in the committed map (task 3): a
# base signature (card_types, subtypes, base P/T) shared by more than one
# distinct grpId. Colour separates the first pair; it cannot separate the
# second (both black), so those stay unstamped.
HUMAN_COPY_TOK, HUMAN_GEN_TOK = 93797, 94158  # 1/1 red vs 1/1 white Human
RAT_COPY_TOK, RAT_GEN_TOK = 93883, 94169      # 1/1 black Rat, copy vs generic
# A copy token whose map "base P/T" (16/16) is really modal OBSERVED P/T: the
# real card's power/toughness is characteristic-defining (dynamic).
CDA_COPY_TOK = 93951  # Consuming Aberration copy, black/blue Horror


def token_obj(
    iid: int,
    grp: int,
    seat: int,
    subtypes: list[str],
    power: int | None = None,
    toughness: int | None = None,
    card_types: tuple[str, ...] = ("CardType_Creature",),
) -> GameObject:
    """A GRE battlefield token object."""
    return GameObject(
        instance_id=iid, grp_id=grp, type="GameObjectType_Token", zone_id=BF1,
        owner_seat_id=seat, controller_seat_id=seat, visibility="Visibility_Public",
        card_types=list(card_types),
        subtypes=[f"SubType_{s}" for s in subtypes],
        power=power, toughness=toughness,
    )


def add_engine_token(
    ex, seat: int, name: str, subtypes: list[str],
    power: int, toughness: int, colors=None,
):
    """Place an id-less engine token on *seat*'s battlefield (as a card mints one).

    *colors* is an optional set of ``engine.types.Color`` — the explicit colour
    a token impl declares (e.g. ``token.colors = {Color.WHITE}``). Left unset the
    token carries no colour declaration at all — UNDECLARED/UNKNOWN colour,
    mirroring an impl that never states its colour. Pass ``colors=set()`` for a
    token that POSITIVELY establishes explicit colourlessness; the two are not
    equivalent (unknown colour is absence of evidence, not colourlessness).
    """
    from engine.card import Creature
    from engine.types import Zone as EZone

    tok = Creature(
        name=name, subtypes=set(subtypes), base_power=power, base_toughness=toughness,
    )
    tok.is_token = True
    if colors is not None:
        tok.colors = set(colors)
    tok.owner = ex.players[seat]
    tok.controller = ex.players[seat]
    ex.players[seat].zones[EZone.BATTLEFIELD].add(tok)
    return tok


class TestTokenCorrelation:
    """Phase E task 2: id-less engine tokens are stamped with their GRE grpId,
    matched via the token identity map, and then survive sync."""

    def test_idless_engine_token_stamped_from_map(self):
        """A minted, id-less engine token gains the GRE token's grpId and lives."""
        gre = token_obj(500, RABBIT_TOK, 1, ["Rabbit"], 1, 1)
        s0 = snapshot(1, battlefield={1: [500]}, objects={500: gre})
        ex = make_executor([s0])
        tok = add_engine_token(ex, 1, "Rabbit", ["Rabbit"], 1, 1)
        assert getattr(tok, "_grp_id", None) is None
        ex._correlate_tokens(s0)
        assert tok._grp_id == RABBIT_TOK
        assert RABBIT_TOK in ex._minted_token_grpids
        from engine.types import Zone as EZone
        assert tok in ex.players[1].zones[EZone.BATTLEFIELD].get_all()

    def test_matched_token_survives_sync_unmatched_removed(self):
        """Overflow removes only the genuinely-unmatched id-less token."""
        from engine.types import Zone as EZone

        gre = token_obj(500, RABBIT_TOK, 1, ["Rabbit"], 1, 1)
        s0 = snapshot(1, battlefield={1: [500]}, objects={500: gre})
        ex = make_executor([s0])
        rabbit = add_engine_token(ex, 1, "Rabbit", ["Rabbit"], 1, 1)
        stray = add_engine_token(ex, 1, "Goblin", ["Goblin"], 1, 1)  # no GRE counterpart
        ex._sync_zones(s0)
        bf = ex.players[1].zones[EZone.BATTLEFIELD].get_all()
        assert rabbit in bf and rabbit._grp_id == RABBIT_TOK
        assert stray not in bf  # unmatched id-less token is overflow-removed

    def test_ambiguity_matched_by_count(self):
        """Same-signature tokens are interchangeable — matched by count.

        Two GRE Cats and three id-less engine Cats: exactly two are stamped;
        the surplus stays id-0 and is removed by the overflow pass.
        """
        from engine.types import Zone as EZone

        objs = {
            510: token_obj(510, CAT_TOK, 1, ["Cat"], 1, 1),
            511: token_obj(511, CAT_TOK, 1, ["Cat"], 1, 1),
        }
        s0 = snapshot(1, battlefield={1: [510, 511]}, objects=objs)
        ex = make_executor([s0])
        cats = [add_engine_token(ex, 1, "Cat", ["Cat"], 1, 1) for _ in range(3)]
        ex._sync_zones(s0)
        bf = ex.players[1].zones[EZone.BATTLEFIELD].get_all()
        stamped = [c for c in cats if getattr(c, "_grp_id", None) == CAT_TOK]
        assert len(stamped) == 2
        assert all(c in bf for c in stamped)
        assert sum(1 for c in cats if c in bf) == 2  # third removed as overflow

    def test_dragon_disambiguated_by_base_pt(self):
        """Two same-subtype/color tokens (Dragon 4/4 vs 5/5) split by base P/T."""
        objs = {
            520: token_obj(520, DRAGON4_TOK, 1, ["Dragon"], 4, 4),
            521: token_obj(521, DRAGON5_TOK, 1, ["Dragon"], 5, 5),
        }
        s0 = snapshot(1, battlefield={1: [520, 521]}, objects=objs)
        ex = make_executor([s0])
        d4 = add_engine_token(ex, 1, "Dragon", ["Dragon"], 4, 4)
        d5 = add_engine_token(ex, 1, "Dragon", ["Dragon"], 5, 5)
        ex._correlate_tokens(s0)
        assert d4._grp_id == DRAGON4_TOK
        assert d5._grp_id == DRAGON5_TOK

    def test_unmatched_signature_stays_idless(self):
        """An engine token whose signature no GRE token matches keeps id-0."""
        gre = token_obj(500, RABBIT_TOK, 1, ["Rabbit"], 1, 1)
        s0 = snapshot(1, battlefield={1: [500]}, objects={500: gre})
        ex = make_executor([s0])
        other = add_engine_token(ex, 1, "Zombie", ["Zombie"], 2, 2)
        ex._correlate_tokens(s0)
        assert getattr(other, "_grp_id", None) is None


class TestTokenCorrelationAmbiguity:
    """Identity-safety (PR #36): a signature several DISTINCT grpIds share
    map-wide is COLLIDING, and every engine object carrying it is validated
    against the COMPLETE collision set — its explicit colour, then its copy-card
    name — with output restricted to the identities GRE actually contains. It is
    NEVER distributed by grpId/zone order, NOR inferred from being the only
    colliding identity a snapshot happens to show. Ambiguity is decided map-wide
    (``signature_candidates``), so a lone colliding identity still runs full
    validation instead of the count-only path.
    """

    def _color(self):
        from engine.types import Color

        return Color

    def _group(self, entries):
        """Build a battlefield snapshot from (iid, grpId, subtype) tuples."""
        objs = {
            iid: token_obj(iid, grp, 1, [sub], 1, 1) for iid, grp, sub in entries
        }
        return snapshot(1, battlefield={1: list(objs)}, objects=objs)

    def _human_group(self):
        """A GRE group holding both 1/1 Human identities (93797 red, 94158 white)."""
        return self._group(
            [(530, HUMAN_COPY_TOK, "Human"), (531, HUMAN_GEN_TOK, "Human")]
        )

    def _rat_group(self):
        """A GRE group holding both 1/1 black Rat identities (93883, 94169)."""
        return self._group(
            [(540, RAT_COPY_TOK, "Rat"), (541, RAT_GEN_TOK, "Rat")]
        )

    # -- Co-present collisions: colour splits Humans; only copy evidence splits Rats

    def test_human_collision_split_by_colour_engine_order_red_first(self):
        Color = self._color()
        ex = make_executor([self._human_group()])
        red = add_engine_token(
            ex, 1, "Dragon Trainer", ["Human"], 1, 1, colors={Color.RED}
        )
        white = add_engine_token(
            ex, 1, "Human", ["Human"], 1, 1, colors={Color.WHITE}
        )
        ex._correlate_tokens(ex.replay.snapshots[0])
        assert red._grp_id == HUMAN_COPY_TOK
        assert white._grp_id == HUMAN_GEN_TOK
        assert ex._minted_token_grpids == {HUMAN_COPY_TOK, HUMAN_GEN_TOK}

    def test_human_collision_split_by_colour_engine_order_white_first(self):
        """Reversed engine insertion order — must NOT swap identities (the
        exact bug in PR #35's sorted-order distribution). Reversed-order
        co-occurrence coverage per the task."""
        Color = self._color()
        ex = make_executor([self._human_group()])
        white = add_engine_token(
            ex, 1, "Human", ["Human"], 1, 1, colors={Color.WHITE}
        )
        red = add_engine_token(
            ex, 1, "Dragon Trainer", ["Human"], 1, 1, colors={Color.RED}
        )
        ex._correlate_tokens(ex.replay.snapshots[0])
        assert red._grp_id == HUMAN_COPY_TOK
        assert white._grp_id == HUMAN_GEN_TOK
        assert ex._minted_token_grpids == {HUMAN_COPY_TOK, HUMAN_GEN_TOK}

    def test_same_colour_generic_rats_left_unstamped(self):
        """93883 and 94169 are both 1/1 BLACK Rats: colour can't tell them apart
        and two GENERIC engine Rats carry no copy evidence either, so neither is
        stamped and neither grpId is marked producible (honest ambiguity)."""
        Color = self._color()
        ex = make_executor([self._rat_group()])
        r1 = add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        r2 = add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        ex._correlate_tokens(ex.replay.snapshots[0])
        assert getattr(r1, "_grp_id", None) is None
        assert getattr(r2, "_grp_id", None) is None
        assert not (ex._minted_token_grpids & {RAT_COPY_TOK, RAT_GEN_TOK})

    def test_same_colour_rat_correlates_only_with_copy_evidence(self):
        """Same-colour Rats: the COPY is stamped from reliable copy-name evidence
        (Burglar Rat → 93883) while the generic Rat, which no reliable
        discriminator separates from the copy, stays id-less."""
        Color = self._color()
        ex = make_executor([self._rat_group()])
        copy = add_engine_token(
            ex, 1, "Burglar Rat", ["Rat"], 1, 1, colors={Color.BLACK}
        )
        generic = add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        ex._correlate_tokens(ex.replay.snapshots[0])
        assert copy._grp_id == RAT_COPY_TOK
        assert getattr(generic, "_grp_id", None) is None
        assert ex._minted_token_grpids == {RAT_COPY_TOK}

    def test_same_colour_rat_copy_evidence_order_independent(self):
        """Reversed engine insertion order — the copy still resolves to 93883 and
        the generic stays id-less: order never decides identity. Reversed-order
        co-occurrence coverage per the task."""
        Color = self._color()
        ex = make_executor([self._rat_group()])
        generic = add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        copy = add_engine_token(
            ex, 1, "Burglar Rat", ["Rat"], 1, 1, colors={Color.BLACK}
        )
        ex._correlate_tokens(ex.replay.snapshots[0])
        assert copy._grp_id == RAT_COPY_TOK
        assert getattr(generic, "_grp_id", None) is None
        assert ex._minted_token_grpids == {RAT_COPY_TOK}

    def test_undeclared_colour_token_not_stamped_in_collision(self):
        """An engine token in a colliding signature that declares NO colour
        reads as UNKNOWN colour — absence of evidence that establishes no
        candidate — so it stays unstamped rather than guessed."""
        ex = make_executor([self._human_group()])
        # No colour set -> _engine_token_color_key(t) is None (UNKNOWN): it
        # narrows nothing and establishes nothing, so no candidate resolves.
        t = add_engine_token(ex, 1, "Human", ["Human"], 1, 1)
        ex._correlate_tokens(ex.replay.snapshots[0])
        assert getattr(t, "_grp_id", None) is None

    # -- Individually-present collisions: snapshot presence never proves identity

    def test_red_engine_human_not_stamped_when_only_white_present(self):
        """GRE shows only the white Human 94158, but the engine object is an
        explicit RED 1/1 Human. Its colour resolves to the red copy 93797 — an
        identity GRE does not contain here — so it is left id-less, NEVER stamped
        94158 just because 94158 is the only colliding Human present."""
        Color = self._color()
        s0 = self._group([(530, HUMAN_GEN_TOK, "Human")])
        ex = make_executor([s0])
        red = add_engine_token(
            ex, 1, "Dragon Trainer", ["Human"], 1, 1, colors={Color.RED}
        )
        ex._correlate_tokens(s0)
        assert getattr(red, "_grp_id", None) is None
        assert HUMAN_GEN_TOK not in ex._minted_token_grpids
        assert HUMAN_COPY_TOK not in ex._minted_token_grpids

    def test_white_engine_human_not_stamped_when_only_red_copy_present(self):
        """GRE shows only the red Human copy 93797, but the engine object is an
        explicit WHITE 1/1 Human. Colour resolves it to the white 94158 — absent
        here — so it is left id-less, NEVER stamped 93797."""
        Color = self._color()
        s0 = self._group([(530, HUMAN_COPY_TOK, "Human")])
        ex = make_executor([s0])
        white = add_engine_token(ex, 1, "Human", ["Human"], 1, 1, colors={Color.WHITE})
        ex._correlate_tokens(s0)
        assert getattr(white, "_grp_id", None) is None
        assert HUMAN_COPY_TOK not in ex._minted_token_grpids
        assert HUMAN_GEN_TOK not in ex._minted_token_grpids

    def test_burglar_rat_copy_not_stamped_when_only_generic_present(self):
        """GRE shows only the generic Rat 94169, but the engine object is a
        Burglar Rat COPY. Copy-name evidence positively identifies it as 93883 —
        which GRE does not contain here — so it is left id-less, NEVER stamped
        94169 (the only colliding Rat the snapshot shows)."""
        Color = self._color()
        s0 = self._group([(540, RAT_GEN_TOK, "Rat")])
        ex = make_executor([s0])
        rat = add_engine_token(
            ex, 1, "Burglar Rat", ["Rat"], 1, 1, colors={Color.BLACK}
        )
        ex._correlate_tokens(s0)
        assert getattr(rat, "_grp_id", None) is None
        assert RAT_GEN_TOK not in ex._minted_token_grpids
        assert RAT_COPY_TOK not in ex._minted_token_grpids

    def test_single_identity_human_matching_colour_correlates(self):
        """Replaces test_single_identity_in_colliding_signature_count_matches.

        A group showing ONE colliding identity is NOT given the count-only path
        (the signature still collides map-wide). Full identity validation runs;
        because every engine object's colour matches the sole present identity
        (white → 94158, the only white in the Human collision set), each is
        stamped 94158. Correlation rests on matching colour evidence, NOT on
        94158 being the only identity the snapshot shows."""
        Color = self._color()
        s0 = self._group([
            (550, HUMAN_GEN_TOK, "Human"),
            (551, HUMAN_GEN_TOK, "Human"),
            (552, HUMAN_GEN_TOK, "Human"),
        ])
        ex = make_executor([s0])
        humans = [
            add_engine_token(ex, 1, "Human", ["Human"], 1, 1, colors={Color.WHITE})
            for _ in range(3)
        ]
        ex._correlate_tokens(s0)
        assert all(h._grp_id == HUMAN_GEN_TOK for h in humans)
        assert ex._minted_token_grpids == {HUMAN_GEN_TOK}

    def test_colliding_signature_more_engine_than_gre_caps_by_count(self):
        """More engine objects than GRE shows of the resolved identity: only up
        to the GRE count are stamped; the surplus stays id-less (compare/resync
        removes it as overflow)."""
        Color = self._color()
        s0 = self._group([(550, HUMAN_GEN_TOK, "Human")])  # GRE: one white Human
        ex = make_executor([s0])
        whites = [
            add_engine_token(ex, 1, "Human", ["Human"], 1, 1, colors={Color.WHITE})
            for _ in range(3)
        ]
        ex._correlate_tokens(s0)
        stamped = [h for h in whites if getattr(h, "_grp_id", None) == HUMAN_GEN_TOK]
        assert len(stamped) == 1
        assert ex._minted_token_grpids == {HUMAN_GEN_TOK}

    def test_dynamic_pt_copy_not_matched_by_observed_pt(self):
        """The map records 16/16 for the Consuming Aberration copy, but that is
        modal OBSERVED P/T of a characteristic-defining creature. An engine copy
        at its live (different) base P/T is NOT force-matched to that observed
        value — base P/T stays a required filter, so the mismatch leaves the
        token unstamped rather than inventing a match."""
        Color = self._color()
        gre = token_obj(560, CDA_COPY_TOK, 1, ["Horror"], 16, 16)
        s0 = snapshot(1, battlefield={1: [560]}, objects={560: gre})
        ex = make_executor([s0])
        aberration = add_engine_token(
            ex, 1, "Consuming Aberration", ["Horror"], 3, 3,
            colors={Color.BLACK, Color.BLUE},
        )
        ex._correlate_tokens(s0)
        assert getattr(aberration, "_grp_id", None) is None
        assert CDA_COPY_TOK not in ex._minted_token_grpids

    # -- Copy name is a REQUIRED consistency check, even when colour is unique --

    def test_colour_unique_copy_rejected_when_engine_name_contradicts(self):
        """GRE contains the red copy 93797, and the engine object IS a red 1/1
        Human — so colour leaves exactly one candidate — but it is named
        "Human", NOT the copied card "Dragon Trainer". Colour narrowing to one
        candidate must NOT override the contradictory copy name: the token stays
        id-less and 93797 is never marked producible. (Pre-fix, colour-leaves-one
        short-circuited and wrongly stamped it.)"""
        Color = self._color()
        s0 = self._group([(530, HUMAN_COPY_TOK, "Human")])
        ex = make_executor([s0])
        human = add_engine_token(
            ex, 1, "Human", ["Human"], 1, 1, colors={Color.RED}
        )
        ex._correlate_tokens(s0)
        assert getattr(human, "_grp_id", None) is None
        assert HUMAN_COPY_TOK not in ex._minted_token_grpids

    def test_colour_unique_copy_correlates_when_engine_name_matches(self):
        """The consistent counterpart: GRE contains 93797, the engine object is a
        red 1/1 Human named "Dragon Trainer" (the copied card). Colour AND copy
        name agree, so it correlates to 93797."""
        Color = self._color()
        s0 = self._group([(530, HUMAN_COPY_TOK, "Human")])
        ex = make_executor([s0])
        human = add_engine_token(
            ex, 1, "Dragon Trainer", ["Human"], 1, 1, colors={Color.RED}
        )
        ex._correlate_tokens(s0)
        assert human._grp_id == HUMAN_COPY_TOK
        assert ex._minted_token_grpids == {HUMAN_COPY_TOK}

    def test_same_colour_copy_rejected_when_engine_name_is_generic(self):
        """GRE contains the copy 93883; the engine object is a black 1/1 Rat named
        just "Rat". Colour cannot separate 93883 from the generic 94169, and the
        generic name matches neither the copy's recorded "Burglar Rat" nor is it
        positive evidence for the generic — so the token does NOT correlate to
        93883 (nor is 94169 inferred by elimination)."""
        Color = self._color()
        s0 = self._group([(540, RAT_COPY_TOK, "Rat")])
        ex = make_executor([s0])
        rat = add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        ex._correlate_tokens(s0)
        assert getattr(rat, "_grp_id", None) is None
        assert RAT_COPY_TOK not in ex._minted_token_grpids
        assert RAT_GEN_TOK not in ex._minted_token_grpids

    def test_same_colour_copy_correlates_when_engine_name_matches(self):
        """GRE contains 93883; the engine object is a black 1/1 Rat named "Burglar
        Rat". Colour leaves both black Rats, but the copy name affirmatively picks
        the copy 93883 (the generic 94169 is never name-established), so it
        correlates."""
        Color = self._color()
        s0 = self._group([(540, RAT_COPY_TOK, "Rat")])
        ex = make_executor([s0])
        rat = add_engine_token(
            ex, 1, "Burglar Rat", ["Rat"], 1, 1, colors={Color.BLACK}
        )
        ex._correlate_tokens(s0)
        assert rat._grp_id == RAT_COPY_TOK
        assert ex._minted_token_grpids == {RAT_COPY_TOK}

    # -- Unknown colour is NOT positive colourless evidence --

    def _colourless_collision_map(self):
        """A SYNTHETIC colliding signature (2/2 Construct) whose members differ
        only by colour: 700 is a generic COLOURLESS token, 701 a generic RED one.
        No copy names, so colour is the only discriminator — isolating the
        colourless/unknown split cleanly."""
        from silverquillm.replay.executor import TokenIdMap

        base = {
            "card_types": ["Creature"], "subtypes": ["Construct"],
            "base_power": 2, "base_toughness": 2, "name": None,
        }
        return TokenIdMap({"tokens": {
            "700": {**base, "colors": [], "label": "2/2 colourless Construct"},
            "701": {**base, "colors": ["Red"], "label": "2/2 red Construct"},
        }})

    def test_unknown_colour_does_not_select_colourless_candidate(self):
        """An engine token that declares NO colour (unknown, not colourless) must
        NOT be matched to the colourless candidate 700 by colour equality: unknown
        colour is the absence of evidence, and with no copy name to resolve it the
        token stays id-less."""
        ex = make_executor([snapshot(1)])
        ex.token_map = self._colourless_collision_map()
        candidates = ex.token_map.signature_candidates(ex.token_map.signature(700))
        assert candidates == {700, 701}
        # colours=None (default) → the token declares no colour → UNKNOWN.
        tok = add_engine_token(ex, 1, "Construct", ["Construct"], 2, 2)
        assert ex._engine_token_color_key(tok) is None
        assert ex._resolve_colliding_identity(tok, candidates) is None

    def test_explicit_colourless_selects_colourless_candidate_when_unique(self):
        """An engine token that EXPLICITLY establishes colourlessness (empty
        ``colors`` set) is positive evidence: colour equality isolates the sole
        colourless candidate 700 (701 is red), and with the remaining evidence
        unique it resolves to 700."""
        ex = make_executor([snapshot(1)])
        ex.token_map = self._colourless_collision_map()
        candidates = ex.token_map.signature_candidates(ex.token_map.signature(700))
        # colours=set() → an explicit, empty colour set → positive colourless.
        tok = add_engine_token(
            ex, 1, "Construct", ["Construct"], 2, 2, colors=set()
        )
        assert ex._engine_token_color_key(tok) == frozenset()
        assert ex._resolve_colliding_identity(tok, candidates) == 700


class TestTokenMapCollisionAudit:
    """Task 3: every committed-map base-signature shared by more than one grpId
    is enumerated with the EXACT runtime signature (``TokenIdMap.signature``),
    not a script-only signature, and is classified. This guards against map
    drift silently introducing a new, undocumented collision that correlation
    would then have to guess through.
    """

    def _map(self):
        from silverquillm.replay.executor import load_token_id_map

        return load_token_id_map()

    def test_runtime_signature_collisions_are_exactly_the_documented_two(self):
        from collections import defaultdict

        tm = self._map()
        by_sig: dict = defaultdict(set)
        for grp in tm.known_grp_ids():
            sig = tm.signature(grp)
            if sig is not None:
                by_sig[sig].add(grp)
        collisions = {frozenset(g) for g in by_sig.values() if len(g) > 1}
        assert collisions == {
            frozenset({HUMAN_COPY_TOK, HUMAN_GEN_TOK}),
            frozenset({RAT_COPY_TOK, RAT_GEN_TOK}),
        }

    def test_human_collision_is_colour_separable(self):
        # 93797 (red) vs 94158 (white): colour disambiguates → both stampable.
        tm = self._map()
        assert tm.color_key(HUMAN_COPY_TOK) != tm.color_key(HUMAN_GEN_TOK)

    def test_rat_collision_is_not_colour_separable(self):
        # 93883 vs 94169: both black → colour cannot disambiguate; only the copy
        # (93883, name "Burglar Rat") carries a reliable copy-name discriminator.
        tm = self._map()
        assert tm.color_key(RAT_COPY_TOK) == tm.color_key(RAT_GEN_TOK)
        assert tm.token_name(RAT_COPY_TOK) and not tm.token_name(RAT_GEN_TOK)

    def test_every_collision_member_takes_colliding_path_alone(self):
        """Each collision member routes through the globally-ambiguous path even
        when it would be the ONLY identity present: its runtime signature maps to
        more than one grpId map-wide (``signature_candidates``), so correlation
        can never take the count-only branch for it — the core PR #36 fix."""
        tm = self._map()
        for grp in (HUMAN_COPY_TOK, HUMAN_GEN_TOK, RAT_COPY_TOK, RAT_GEN_TOK):
            candidates = tm.signature_candidates(tm.signature(grp))
            assert grp in candidates
            assert len(candidates) >= 2, (
                f"grpId {grp} must be on the colliding path, got {candidates}"
            )

    def test_noncolliding_token_is_alone_on_its_signature(self):
        """A control: a non-colliding token (the 1/1 Rabbit) is the sole holder
        of its signature, so it keeps the count-only unambiguous path."""
        tm = self._map()
        assert tm.signature_candidates(tm.signature(RABBIT_TOK)) == {RABBIT_TOK}


class TestObserverCreationPathsGrpId:
    """Task 5: the ``_grp_id`` tags added at card creation are simulate-only, so
    observer mode's ``_card_to_grp_id`` keeps its pre-Phase-E name reverse-lookup
    behaviour — observer output stays byte-identical to the baseline."""

    def _executor(self, simulate):
        replay = ReplayGame(seat_id=1, opponent_seat_id=2)
        replay.snapshots = [snapshot(1)]
        ex = ReplayExecutor(
            replay=replay, card_id_map=dict(CARD_MAP), registry=None, simulate=simulate
        )
        ex.initialize(replay.snapshots[0])
        return ex

    def test_basic_card_grpid_tagged_only_in_simulate(self):
        obs = self._executor(simulate=False)
        card = obs._create_basic_card(FOREST, "Forest", obs.players[1])
        assert not getattr(card, "_grp_id", None)
        sim = self._executor(simulate=True)
        card2 = sim._create_basic_card(FOREST, "Forest", sim.players[1])
        assert card2._grp_id == FOREST

    def test_create_card_fallback_grpid_tagged_only_in_simulate(self):
        # registry=None routes _create_card through the basic-land fallback.
        obs = self._executor(simulate=False)
        card = obs._create_card(FOREST, obs.players[1])
        assert not getattr(card, "_grp_id", None)
        sim = self._executor(simulate=True)
        card2 = sim._create_card(FOREST, sim.players[1])
        assert card2._grp_id == FOREST

    def test_create_card_registry_path_grpid_tagged_only_in_simulate(self):
        from engine.card import CardImpl

        class _CreatingRegistry:
            def __contains__(self, name):
                return name == "Forest"

            def create_instance(self, name, owner=None):
                return CardImpl(name=name, owner=owner)

        obs = self._executor(simulate=False)
        obs.registry = _CreatingRegistry()
        card = obs._create_card(FOREST, obs.players[1])
        assert not getattr(card, "_grp_id", None)
        sim = self._executor(simulate=True)
        sim.registry = _CreatingRegistry()
        card2 = sim._create_card(FOREST, sim.players[1])
        assert card2._grp_id == FOREST


class TestTokenMissingSemantics:
    """Phase E task 6: a mapped token the engine produces is not missing; one it
    never produces still surfaces, as its named token identity."""

    def _missing(self, validator):
        from silverquillm.replay.validation import DivergenceType

        return [
            d for d in validator.divergences
            if d.divergence_type == DivergenceType.MISSING_CARD
        ]

    def test_produced_token_is_not_missing(self):
        """A token the engine mints and correlates clears MISSING_CARD."""
        gre = token_obj(500, RABBIT_TOK, 1, ["Rabbit"], 1, 1)
        snaps = [
            snapshot(1),
            snapshot(2, battlefield={1: [500]}, objects={500: gre}),
        ]
        ex, validator = make_validator(snaps, FakeRegistry({"Plains"}))
        add_engine_token(ex, 1, "Rabbit", ["Rabbit"], 1, 1)
        validator.execute_all()
        validator.report()
        assert self._missing(validator) == []
        assert RABBIT_TOK in ex._minted_token_grpids

    def test_unproduced_token_surfaces_named_not_anonymous(self):
        """A mapped token the engine never mints surfaces as its named identity,
        not an anonymous grpId_<n>."""
        gre = token_obj(500, CAT_TOK, 1, ["Cat"], 1, 1)
        snaps = [
            snapshot(1),
            snapshot(2, battlefield={1: [500]}, objects={500: gre}),
        ]
        ex, validator = make_validator(snaps, FakeRegistry({"Plains"}))
        validator.execute_all()
        validator.report()
        missing = self._missing(validator)
        assert len(missing) == 1
        assert CAT_TOK not in ex._minted_token_grpids
        assert "Cat token" in missing[0].description
        assert f"grpId_{CAT_TOK}" not in missing[0].description

    def test_ambiguous_correlation_does_not_mark_producible_or_suppress_missing(self):
        """An ambiguous match must NOT contaminate producibility. Both black-Rat
        identities (93883 copy, 94169 generic) share a signature colour can't
        split; the engine mints two GENERIC black Rats (no copy evidence), so
        neither grpId is stamped, neither is marked producible, and the generic
        identity still surfaces as MISSING. Under PR #35 the sorted-order
        assignment would stamp both, mark 94169 producible, and wrongly suppress
        its MISSING_CARD entry.
        """
        from engine.types import Color

        # Mirror the real card_id_map: the copy grpId resolves to its real card
        # (Burglar Rat, registered → never missing); the generic grpId has no
        # card_id_map entry and resolves via its token label.
        card_map = dict(CARD_MAP) | {RAT_COPY_TOK: "Burglar Rat"}
        objs = {
            540: token_obj(540, RAT_COPY_TOK, 1, ["Rat"], 1, 1),
            541: token_obj(541, RAT_GEN_TOK, 1, ["Rat"], 1, 1),
        }
        snaps = [snapshot(1), snapshot(2, battlefield={1: [540, 541]}, objects=objs)]
        ex, validator = make_validator(
            snaps, FakeRegistry({"Plains", "Burglar Rat"}), card_map=card_map
        )
        # Two generic Rats: colour cannot split them and neither name matches the
        # copy candidate, so the match is genuinely ambiguous.
        add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        validator.execute_all()
        validator.report()
        # Ambiguous → neither identity marked producible.
        assert RAT_COPY_TOK not in ex._minted_token_grpids
        assert RAT_GEN_TOK not in ex._minted_token_grpids
        # The unproven generic identity is not suppressed — it surfaces missing.
        missing = self._missing(validator)
        assert any(RAT_GEN_TOK in d.involved_grp_ids for d in missing)

    def test_copy_evidence_correlation_marks_producible_and_clears_missing(self):
        """The flip side of the ambiguity guard: a same-colour token the copy-name
        evidence DOES resolve (Burglar Rat → 93883) is marked producible and so
        clears its own MISSING entry, while the generic identity it collides with
        is neither correlated nor suppressed — it still surfaces MISSING.
        """
        from engine.types import Color

        # Neither Rat is in the card_map: both resolve via their token label, so
        # an uncorrelated identity WOULD surface missing — producibility is what
        # clears the copy's entry.
        objs = {
            540: token_obj(540, RAT_COPY_TOK, 1, ["Rat"], 1, 1),
            541: token_obj(541, RAT_GEN_TOK, 1, ["Rat"], 1, 1),
        }
        snaps = [snapshot(1), snapshot(2, battlefield={1: [540, 541]}, objects=objs)]
        ex, validator = make_validator(snaps, FakeRegistry({"Plains"}))
        add_engine_token(ex, 1, "Burglar Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        add_engine_token(ex, 1, "Rat", ["Rat"], 1, 1, colors={Color.BLACK})
        validator.execute_all()
        validator.report()
        assert RAT_COPY_TOK in ex._minted_token_grpids   # copy correlated → producible
        assert RAT_GEN_TOK not in ex._minted_token_grpids  # generic unresolved
        grp_missing = {
            g for d in self._missing(validator) for g in d.involved_grp_ids
        }
        assert RAT_COPY_TOK not in grp_missing  # producible → not missing
        assert RAT_GEN_TOK in grp_missing       # unproven → surfaces missing

    def test_copy_name_contradiction_rejected_does_not_suppress_missing(self):
        """A copy candidate REJECTED on a contradictory name must not be marked
        producible, so it still surfaces MISSING. GRE shows the red copy 93797;
        the engine mints a red 1/1 Human named "Human" (not the copied "Dragon
        Trainer"), so the name contradicts the copy and it is left id-less. 93797
        is therefore NOT producible and — since it is not registered — surfaces
        as its named missing identity, exactly as if no engine token existed."""
        from engine.types import Color

        gre = token_obj(530, HUMAN_COPY_TOK, 1, ["Human"], 1, 1)
        snaps = [snapshot(1), snapshot(2, battlefield={1: [530]}, objects={530: gre})]
        ex, validator = make_validator(snaps, FakeRegistry({"Plains"}))
        # Red 1/1 Human, but named "Human" — contradicts the copy's "Dragon
        # Trainer", so correlation rejects it (colour-unique but name-mismatched).
        add_engine_token(ex, 1, "Human", ["Human"], 1, 1, colors={Color.RED})
        validator.execute_all()
        validator.report()
        assert HUMAN_COPY_TOK not in ex._minted_token_grpids  # rejected → not producible
        grp_missing = {
            g for d in self._missing(validator) for g in d.involved_grp_ids
        }
        assert HUMAN_COPY_TOK in grp_missing  # rejection does not suppress MISSING


class TestActivationTargetIntent:
    """Phase E task 4: an activated ability's activation-time target query is
    answered from the replay stream — TargetSpec keyed to the ability's own
    instance id — via _with_target_intent."""

    def test_activation_intent_started_from_ability_targetspec(self):
        victim = card_obj(150, FOREST, 2, BF1)
        ts = Annotation(
            id=902, affector_id=700, affected_ids=[150],
            type=["AnnotationType_TargetSpec"], details={"index": [1]},
        )
        s0 = snapshot(1, battlefield={2: [150]}, objects={150: victim})
        s1 = snapshot(2, battlefield={2: [150]}, objects={150: victim},
                      annotations=[ts])
        ex = make_executor([s0, s1])
        player = ex.players[1]
        started: dict = {}
        orig_start = player.start_intent

        def spy(name, intent):
            started["name"] = name
            started["prefs"] = intent.preferences
            return orig_start(name, intent)

        player.start_intent = spy
        action = ReplayAction(
            action_type="ability_activation", player_seat_id=1, instance_id=700,
        )
        ex._with_target_intent(action, s0, s1, lambda: None)
        assert started.get("name") == "replay_ability_700"
        assert started.get("prefs")  # the ability's target was derived + applied


class TestMultiAbilityFallthrough:
    """Phase E task 5: a source with more than one activated ability is not
    guess-driven — it falls through to the resync (honest), never activating a
    guessed ability."""

    class _TwoAbilitySource:
        name = "TwoAbilitySource"

        def get_activated_abilities(self):
            from engine.card import ActivatedAbility

            return [
                ActivatedAbility(cost=lambda g, s: True, effect=lambda g: None,
                                 description="a"),
                ActivatedAbility(cost=lambda g, s: True, effect=lambda g: None,
                                 description="b"),
            ]

    def test_multi_ability_source_is_not_driven(self):
        s0 = snapshot(1)
        ex = make_executor([s0])
        source = self._TwoAbilitySource()
        activated = {"count": 0}
        import engine.abilities as ab
        orig = ab.activate_ability

        def spy(*a, **k):
            activated["count"] += 1
            return orig(*a, **k)

        ab.activate_ability = spy
        try:
            action = ReplayAction(
                action_type="ability_activation", player_seat_id=1, instance_id=1,
            )
            result = StepResult(snapshot_id=1)
            ex._try_activate_ability(ex.players[1], source, action, s0, s0, result)
        finally:
            ab.activate_ability = orig
        assert activated["count"] == 0  # never guess-drove an ability
        assert result.engine_failures == []


class TestReplayActivationTimingContext:
    """Phase E task 3: a driven activation runs under GRE-observed-legal timing
    so the sorcery-speed can_activate gate accepts it, without weakening the
    gate for the engine's own path (engine_tests cover non-replay strictness)."""

    def test_context_supplies_sorcery_legal_timing_and_restores(self):
        from engine.casting import is_sorcery_speed
        from engine.types import Phase

        s0 = snapshot(1)
        ex = make_executor([s0])
        game = ex.game
        # Simulate the GRE turn_info lagging into combat while the opponent is
        # the engine's active player — is_sorcery_speed is False for seat 1.
        game.phase = Phase.COMBAT
        game.active_player_index = 1
        p1 = ex.players[1]
        assert not is_sorcery_speed(game, p1)
        with ex._replay_activation_context(p1):
            # Inside the context the observed-legal timing is supplied.
            assert is_sorcery_speed(game, p1)
        # State restored afterward — nothing leaks into comparison.
        assert game.phase == Phase.COMBAT
        assert game.active_player_index == 1

    def test_context_preserves_an_existing_main_phase(self):
        from engine.types import Phase

        s0 = snapshot(1)
        ex = make_executor([s0])
        game = ex.game
        game.phase = Phase.POSTCOMBAT_MAIN
        game.active_player_index = 0
        with ex._replay_activation_context(ex.players[1]):
            # Already a main phase — kept, not overridden to precombat.
            assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.active_player_index == 0


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

    def test_pending_counter_object_gets_no_oracle_correction(self):
        """A permanent whose GRE counter is still deferred is skipped by the
        resync's P/T correction. Otherwise a +N/+N correction installed for the
        then-missing counter would double-count against the counter when it lands
        next snapshot (the enter-with-counters 0/0-creature case). Once the
        counter is no longer pending, the gap is corrected normally."""
        ex = make_executor([self._bf_snap(1, 2, 2)])  # engine creature is 2/2
        gre = self._bf_snap(2, 4, 4)                    # GRE shows 4/4 (missing +2/+2)

        # Counter deferred (uncorrelated ETB) -> the object is skipped: no
        # correction, so nothing to double-count when the counter lands.
        ex._pending_counter_effects[(999, 100)] = {
            "name": "+1/+1", "is_add": True, "amount": 2,
        }
        ex._rederive_pt_corrections(gre)
        assert ex._oracle_pt_corrections() == []

        # Same gap, no pending counter -> the correction IS installed.
        ex._pending_counter_effects.clear()
        ex._rederive_pt_corrections(gre)
        assert len(ex._oracle_pt_corrections()) == 1
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
        # A partial-mutation untap that raises ProtocolError still re-raises for
        # classification — but only AFTER the operational domain is made safe:
        # the deterministic fallback finishes the untap and NO ENGINE_ERROR is
        # recorded (protocol classification is never converted).
        from engine.decisions import ProtocolError

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)
        card = ex._engine_cards[103]
        card.is_tapped = True
        card.summoning_sick = True
        ex.players[1].land_plays_remaining = 0

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(ProtocolError("boundary failure in untap"), did),
        )

        result = StepResult(snapshot_id=2)
        with pytest.raises(ProtocolError):
            ex._handle_turn_info(self._PREV_TURN, self._CURR_TURN, result)

        # No ENGINE_ERROR recorded for a protocol exception; untap ran once.
        assert result.engine_failures == []
        assert did[0] == 1
        # The fallback restored every untap invariant before propagation, so the
        # operational domain is clean despite the propagating protocol exception.
        assert card.is_tapped is False
        assert card.summoning_sick is False
        assert ex.players[1].land_plays_remaining == 1
        assert ex._operational_dirty is False

    def test_untap_unmatched_query_error_propagates(self, monkeypatch):
        # Same operational-barrier behavior for a QUERY_UNANSWERED-class untap
        # failure: repair deterministically, record no ENGINE_ERROR, re-raise.
        from engine.decisions import UnmatchedQueryError

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)
        card = ex._engine_cards[103]
        card.is_tapped = True
        card.summoning_sick = True
        ex.players[1].land_plays_remaining = 0

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(
                UnmatchedQueryError("no intent matched during untap"), did
            ),
        )

        result = StepResult(snapshot_id=2)
        with pytest.raises(UnmatchedQueryError):
            ex._handle_turn_info(self._PREV_TURN, self._CURR_TURN, result)

        assert result.engine_failures == []
        assert did[0] == 1
        assert card.is_tapped is False
        assert card.summoning_sick is False
        assert ex.players[1].land_plays_remaining == 1
        assert ex._operational_dirty is False

    def test_untap_protocol_error_with_failing_fallback_latches_dirty(
        self, monkeypatch
    ):
        # Protocol untap failure whose deterministic repair CANNOT complete: the
        # exception still propagates for classification, but the operational
        # domain is latched dirty first (fail-closed), never left silently clean.
        from engine.decisions import ProtocolError

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(ProtocolError("boundary failure in untap"), did),
        )
        fallback_calls = [0]

        def _failing_fallback(result=None):
            fallback_calls[0] += 1
            return False

        monkeypatch.setattr(ex, "_fallback_untap", _failing_fallback)

        with pytest.raises(ProtocolError):
            ex._handle_turn_info(self._PREV_TURN, self._CURR_TURN, StepResult(snapshot_id=2))

        # The protocol path invoked the fallback (no result argument, so it can
        # record no ENGINE_ERROR) and latched dirty when it returned False.
        assert fallback_calls[0] == 1
        assert ex._operational_dirty is True

    def test_fallback_untap_protocol_error_propagates(self):
        # The real fallback's own protocol branch: latch operational dirtiness
        # BEFORE propagating, so a protocol failure mid-repair can never be
        # mistaken for a clean untap once the P/T resync restores the surfaces.
        from engine.decisions import ProtocolError
        from engine.types import Zone

        snaps = [self._bf(1, turn=1)]
        ex = make_executor(snaps)
        assert ex._operational_dirty is False

        def _boom():
            raise ProtocolError("boundary failure in fallback")

        ex.game.active_player.zones[Zone.BATTLEFIELD].get_all = _boom
        with pytest.raises(ProtocolError):
            ex._fallback_untap(StepResult(snapshot_id=1))
        assert ex._operational_dirty is True  # latched fail-closed before raise


class TestValidatorUntapProtocolLifecycle:
    """Protocol untap failures obey the operational barrier through the REAL
    ``ValidatingExecutor`` lifecycle (not only direct ``_handle_turn_info``
    calls).

    A ``ProtocolError`` / ``UnmatchedQueryError`` from the turn-boundary untap
    (or from the deterministic fallback) is re-raised for classification — the
    validator records it as PROTOCOL_ERROR / QUERY_UNANSWERED and resyncs only
    the compared / P/T surfaces. The barrier under test: recording that
    divergence must not let the next transition run from half-untapped
    operational state. So each test asserts BOTH the current step's
    classification AND the next step's behavior:

      - fallback repairs -> operational domain clean -> next transition measured;
      - fallback cannot repair -> operational domain latched dirty -> the
        post-exception P/T resync (which sets _synced True) cannot promote it,
        and the next transition is suppressed as REPLAY_INFRA.
    """

    CREATURE = 560000  # unmapped grpId -> Creature shell

    def _bf(self, gsid, *, turn):
        obj = card_obj(
            104, self.CREATURE, 1, BF1,
            card_types=["CardType_Creature"], power=2, toughness=2,
        )
        return snapshot(
            gsid, turn=turn, active=1,
            battlefield={1: [104]}, objects={104: obj},
        )

    @staticmethod
    def _partial_then_raise(exc, did):
        """A broken untap_step: untap ``is_tapped`` on the active player's
        permanents (partial mutation), then raise before summoning sickness and
        land plays are restored. ``did`` counts invocations."""
        def broken(game):
            from engine.types import Zone
            did[0] += 1
            active = game.active_player
            for card in active.zones[Zone.BATTLEFIELD].get_all():
                if hasattr(card, "is_tapped"):
                    card.is_tapped = False
            raise exc
        return broken

    @staticmethod
    def _of_type(validator, dtype):
        return [d for d in validator.divergences if d.divergence_type == dtype]

    def test_protocol_error_recorded_and_repaired_next_step_measured(
        self, monkeypatch
    ):
        from engine.decisions import ProtocolError
        from silverquillm.replay.validation import DivergenceType

        # Boundary is the first transition; the second transition is the follow-up.
        snaps = [self._bf(1, turn=1), self._bf(2, turn=2), self._bf(3, turn=2)]
        ex, validator = make_validator(snaps, None)
        # Operational state the deterministic fallback must repair.
        ex._engine_cards[104].summoning_sick = True
        ex.players[1].land_plays_remaining = 0

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(ProtocolError("boundary failure in untap"), did),
        )

        results = validator.execute_all()

        # Boundary transition (gsId 2): exactly one PROTOCOL_ERROR, no ENGINE_ERROR.
        protocol = self._of_type(validator, DivergenceType.PROTOCOL_ERROR)
        assert len(protocol) == 1
        assert protocol[0].game_state_id == 2
        assert self._of_type(validator, DivergenceType.ENGINE_ERROR) == []
        assert did[0] == 1  # untap_step ran once; the fallback did not retry it

        # The deterministic fallback repaired the operational domain, so the
        # executor ends fully synchronized and NOTHING was suppressed.
        assert ex._operational_dirty is False
        assert ex._fully_synced is True
        assert self._of_type(validator, DivergenceType.REPLAY_INFRA) == []
        # The repair actually happened — summoning sickness cleared and the land
        # play reset (surfaces compare_state never reads, so only the fallback
        # could restore them). Without the protocol-path repair these would stay
        # half-untapped while the executor still reported itself synchronized.
        assert ex._engine_cards[104].summoning_sick is False
        assert ex.players[1].land_plays_remaining == 1

        # The following transition (gsId 2 -> 3) was measured, not suppressed.
        following = results[1]
        assert following.skipped is False
        assert following.mismatches == []

    def test_unmatched_query_error_recorded_and_repaired_next_step_measured(
        self, monkeypatch
    ):
        from engine.decisions import UnmatchedQueryError
        from silverquillm.replay.validation import DivergenceType

        snaps = [self._bf(1, turn=1), self._bf(2, turn=2), self._bf(3, turn=2)]
        ex, validator = make_validator(snaps, None)
        ex._engine_cards[104].summoning_sick = True
        ex.players[1].land_plays_remaining = 0

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(
                UnmatchedQueryError("no intent matched during untap"), did
            ),
        )

        results = validator.execute_all()

        # QUERY_UNANSWERED retains its classification (not converted to
        # ENGINE_ERROR or PROTOCOL_ERROR).
        unanswered = self._of_type(validator, DivergenceType.QUERY_UNANSWERED)
        assert len(unanswered) == 1
        assert unanswered[0].game_state_id == 2
        assert self._of_type(validator, DivergenceType.ENGINE_ERROR) == []
        assert self._of_type(validator, DivergenceType.PROTOCOL_ERROR) == []

        assert ex._operational_dirty is False
        assert self._of_type(validator, DivergenceType.REPLAY_INFRA) == []
        # Operational invariants restored by the deterministic repair.
        assert ex._engine_cards[104].summoning_sick is False
        assert ex.players[1].land_plays_remaining == 1
        assert results[1].skipped is False
        assert results[1].mismatches == []

    def test_unrepairable_protocol_untap_suppresses_next_transition(
        self, monkeypatch
    ):
        # Fail-closed lifecycle + the resync-cannot-promote invariant: when the
        # deterministic fallback cannot complete, the operational domain latches
        # dirty and the post-exception P/T resync (which sets _synced True) can
        # never promote the executor back to fully synchronized.
        from engine.decisions import ProtocolError
        from silverquillm.replay.validation import DivergenceType

        snaps = [self._bf(1, turn=1), self._bf(2, turn=2), self._bf(3, turn=2)]
        ex, validator = make_validator(snaps, None)

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(ProtocolError("boundary failure in untap"), did),
        )
        fallback_calls = [0]

        def _failing_fallback(result=None):
            fallback_calls[0] += 1
            return False  # repair cannot be proven complete

        monkeypatch.setattr(ex, "_fallback_untap", _failing_fallback)

        # Boundary transition: PROTOCOL_ERROR recorded, operational domain dirty.
        boundary = validator.execute_step(snaps[0], snaps[1])
        assert len(self._of_type(validator, DivergenceType.PROTOCOL_ERROR)) == 1
        assert self._of_type(validator, DivergenceType.ENGINE_ERROR) == []
        assert fallback_calls[0] == 1
        # The P/T resync restored the compared surfaces (_synced True) but the
        # operational domain is independent and stays dirty -> not fully synced.
        assert ex._synced is True
        assert ex._operational_dirty is True
        assert ex._fully_synced is False

        # Following transition suppressed as unmeasurable: a REPLAY_INFRA
        # divergence, no comparison from dirty state, and no re-trigger of untap
        # or the fallback during recovery.
        following = validator.execute_step(snaps[1], snaps[2])
        assert following.skipped is True
        assert following.mismatches == []
        infra = self._of_type(validator, DivergenceType.REPLAY_INFRA)
        assert any("unmeasurable" in d.description for d in infra)
        assert did[0] == 1
        assert fallback_calls[0] == 1

    def test_fallback_protocol_exception_preserves_primary_and_suppresses(
        self, monkeypatch
    ):
        # The fallback itself raises a protocol exception after the untap's
        # partial writes. The SECONDARY exception must not replace the PRIMARY
        # untap exception's classification, and the operational domain must be
        # latched dirty so the next transition is suppressed.
        from engine.decisions import ProtocolError, UnmatchedQueryError
        from silverquillm.replay.validation import DivergenceType

        snaps = [self._bf(1, turn=1), self._bf(2, turn=2), self._bf(3, turn=2)]
        ex, validator = make_validator(snaps, None)

        did = [0]
        monkeypatch.setattr(
            "engine.turn.untap_step",
            self._partial_then_raise(
                ProtocolError("PRIMARY untap protocol failure"), did
            ),
        )

        # A fallback that raises a DIFFERENT protocol exception and deliberately
        # does NOT latch the domain — proving the untap protocol path itself
        # latches dirty and re-raises the PRIMARY, never the secondary.
        def _fallback_raises(result=None):
            raise UnmatchedQueryError("SECONDARY failure during untap repair")

        monkeypatch.setattr(ex, "_fallback_untap", _fallback_raises)

        boundary = validator.execute_step(snaps[0], snaps[1])

        # The PRIMARY ProtocolError surfaced; the secondary UnmatchedQueryError
        # did not replace its classification.
        assert len(self._of_type(validator, DivergenceType.PROTOCOL_ERROR)) == 1
        assert self._of_type(validator, DivergenceType.QUERY_UNANSWERED) == []
        # The untap protocol path latched the domain dirty even though the
        # fallback did not.
        assert ex._operational_dirty is True

        following = validator.execute_step(snaps[1], snaps[2])
        assert following.skipped is True
        infra = self._of_type(validator, DivergenceType.REPLAY_INFRA)
        assert any("unmeasurable" in d.description for d in infra)


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
        any failure) AND every name is distinct (the loader hard-fails on a
        duplicate registration). All 286 impls register with zero shadowing."""
        from cards.loader import load_set_registry

        registry = load_set_registry("fdn", strict=True)
        assert len(registry.list_all()) == 286


class TestGoldenGame:
    """Full simulate pipeline over committed corpus games, fingerprint-pinned.

    The fingerprint is intentionally exact: any executor or engine change
    that shifts a game's divergences must be looked at (and the pin updated
    deliberately, justified in the commit message), rather than drowning in
    corpus-level totals. The original game (fdn_match0_game0) pins zero
    ENGINE_ERROR / zero P/T, so it cannot regress the buckets phases A–F moved
    most. Phase F added three fixtures chosen by explicit criteria to cover the
    surfaces this phase moved: token minting (own-ETB), counter/dynamic-P/T
    (the CounterAdded sync), and equipment + activation-funding (the bounded
    funding limitation, pinned as ENGINE_ERROR).
    """

    FIXTURE = REPO_ROOT / "data" / "replays" / "golden" / "fdn_match0_game0.json"
    # Phase F additions.
    FIXTURE_TOKENS = REPO_ROOT / "data" / "replays" / "golden" / "fdn_tokens_prideful.json"
    FIXTURE_COUNTERS = REPO_ROOT / "data" / "replays" / "golden" / "fdn_counters_dynamic_pt.json"
    FIXTURE_EQUIP = REPO_ROOT / "data" / "replays" / "golden" / "fdn_equipment_funding.json"

    @staticmethod
    def _fingerprint(fixture):
        """Run the full simulate pipeline over *fixture*, return its fingerprint."""
        from collections import Counter

        from cards.loader import load_set_registry
        from silverquillm.replay.parser import load_card_id_map, parse_replay
        from silverquillm.replay.validation import ValidatingExecutor

        card_id_map = load_card_id_map()
        registry = load_set_registry("fdn")
        game = parse_replay(fixture, card_id_map=card_id_map)
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
        return report, by_type, by_category

    def test_divergence_fingerprint(self):
        from collections import Counter  # noqa: F401 — used via _fingerprint

        report, by_type, by_category = self._fingerprint(self.FIXTURE)
        # MISSING_CARD is one divergence per (game, identity). Hare Apparent
        # (FDN #15) is implemented, so its occurrences never registered as a
        # missing card; the last remaining missing identity was the engine-minted
        # Rabbit token arrival grpId_94160. Phase E token correlation now stamps
        # that engine token with its GRE grpId (94160) and the MISSING_CARD
        # semantics treat a token the engine actually produces as producible, so
        # it clears: MISSING_CARD 1 -> 0.
        #
        # The 10 STATE_MISMATCH are unchanged and token-independent: the one
        # battlefield entry that mentions 94160 (gsid 93) is a resolution-TIMING
        # divergence — GRE shows the Rabbit a step before the engine's Hare
        # Apparent ETB mints it — not a correlation gap, so it correctly persists
        # (the engine has no Rabbit to correlate at that step). The corpus-wide
        # token zone/P_T cluster is where correlation moves numbers; this game
        # has a single token.
        assert report.total_snapshots == 116
        assert report.successful_comparisons == 109
        assert dict(by_type) == {"STATE_MISMATCH": 10}
        assert dict(by_category) == {
            "zone_contents": 8,
            "life_total": 1,
            "tapped_state": 1,
        }

    def test_tokens_prideful_fingerprint(self):
        """Token-dense game (Prideful Parent ×4). Phase F's own-ETB ordering
        makes Prideful Parent's Cat tokens mint on their own entry; the minted
        tokens correlate and enter the battlefield, so the residual here is the
        token zone-timing surface (GRE shows a token a step before/after the
        engine mints it), not outright MISSING_CARD. Unchanged by the Phase-F
        counter correction: the correction anchors the ledger to the engine
        object (not the GRE aid), so this game's counters land exactly as
        before."""
        report, by_type, by_category = self._fingerprint(self.FIXTURE_TOKENS)
        assert report.total_snapshots == 332
        assert report.successful_comparisons == 313
        assert dict(by_type) == {"STATE_MISMATCH": 24, "ILLEGAL_ACTION": 2}
        assert dict(by_category) == {
            "zone_contents": 22,
            "power_toughness": 2,
            "tapped_state": 2,
        }

    def test_counters_dynamic_pt_fingerprint(self):
        """Counter / dynamic-P/T game. Phase F's CounterAdded sync lands +1/+1
        counters on the correlated permanents, so power_toughness stays bounded
        (12) rather than tracking every counter the executor never fired; the
        remaining P/T is dynamic-P/T cards (e.g. Consuming Aberration) the sync
        does not model."""
        report, by_type, by_category = self._fingerprint(self.FIXTURE_COUNTERS)
        assert report.total_snapshots == 770
        assert report.successful_comparisons == 728
        assert dict(by_type) == {
            "STATE_MISMATCH": 57,
            "ILLEGAL_ACTION": 1,
            "MISSING_CARD": 1,
        }
        assert dict(by_category) == {
            "zone_contents": 32,
            "life_total": 14,
            "power_toughness": 12,
            "MISSING_CARD": 1,
        }

    def test_equipment_funding_fingerprint(self):
        """Equipment + activation-funding game (Goldvein Pick ×30, + tokens +
        counters). The ENGINE_ERROR count (6) is the bounded funding limitation:
        equip activations whose mana GRE recorded only against the equipment's
        cast (or floating/reused, never re-annotated) cannot be funded without
        fabrication, so the equip cost stays unpayable. This fixture pins that
        limitation so a future funding fix (or regression) is visible."""
        report, by_type, by_category = self._fingerprint(self.FIXTURE_EQUIP)
        assert report.total_snapshots == 894
        assert report.successful_comparisons == 809
        assert dict(by_type) == {
            "STATE_MISMATCH": 86,
            "ENGINE_ERROR": 6,
            "ILLEGAL_ACTION": 4,
            "MISSING_CARD": 4,
        }
        assert dict(by_category) == {
            "zone_contents": 56,
            "tapped_state": 19,
            "life_total": 15,
            "ENGINE_ERROR": 6,
            "MISSING_CARD": 4,
        }
