"""Unit tests for the Game Refs registry (engine/refs_registry.py).

The registry is engine-owned: it mints one opaque instance id per game object
(a zone change yields a new object) and assembles GameRefs. Instance ids are
never test-authored.
"""

from __future__ import annotations

from engine.refs_registry import GameRefsRegistry


class _Obj:
    """Stand-in game object."""

    def __init__(self, name: str):
        self.name = name


class TestInstanceIdMinting:
    def test_same_object_same_zone_is_stable(self):
        reg = GameRefsRegistry()
        o = _Obj("bear")
        assert reg.instance_id(o, "battlefield") == reg.instance_id(o, "battlefield")

    def test_distinct_objects_get_distinct_ids(self):
        reg = GameRefsRegistry()
        a, b = _Obj("a"), _Obj("b")
        assert reg.instance_id(a, "battlefield") != reg.instance_id(b, "battlefield")

    def test_zone_change_remints_a_new_object_id(self):
        reg = GameRefsRegistry()
        o = _Obj("bear")
        on_bf = reg.instance_id(o, "battlefield")
        in_gy = reg.instance_id(o, "graveyard")
        assert on_bf != in_gy

    def test_zone_round_trip_mints_fresh_id(self):
        # battlefield -> exile -> battlefield is three stints, three ids: a
        # flickered creature is a new object, not the pre-flicker one.
        reg = GameRefsRegistry()
        o = _Obj("bear")
        first_bf = reg.instance_id(o, "battlefield")
        in_exile = reg.instance_id(o, "exile")
        second_bf = reg.instance_id(o, "battlefield")
        assert len({first_bf, in_exile, second_bf}) == 3
        # Within the new stint the id is stable.
        assert reg.instance_id(o, "battlefield") == second_bf

    def test_note_zone_change_breaks_continuity_for_unobserved_stints(self):
        # move_to_zone calls this hook so a round trip whose middle stint is
        # never observed by a query still re-mints on return.
        reg = GameRefsRegistry()
        o = _Obj("bear")
        pre = reg.instance_id(o, "battlefield")
        reg.note_zone_change(o)  # battlefield -> exile, never observed
        reg.note_zone_change(o)  # exile -> battlefield, never observed
        assert reg.instance_id(o, "battlefield") != pre

    def test_ids_are_not_test_authored(self):
        # The id is opaque/engine-minted; the test cannot predict it beyond
        # uniqueness/stability. We only assert it is hashable.
        reg = GameRefsRegistry()
        iid = reg.instance_id(_Obj("x"), "hand")
        hash(iid)


class TestRefAssembly:
    def test_ref_for_carries_instance_in_object_field(self):
        reg = GameRefsRegistry()
        o = _Obj("bear")
        ref = reg.ref_for(o, zone="battlefield")
        iid = reg.instance_id(o, "battlefield")
        assert ("instance", iid) in ref.object

    def test_ref_for_populates_provenance_fields(self):
        reg = GameRefsRegistry()
        o = _Obj("bear")
        ref = reg.ref_for(
            o,
            zone="battlefield",
            card={"number": "fdn_215"},
            player={"seat": 1},
        )
        assert ("number", "fdn_215") in ref.card
        assert ("seat", 1) in ref.player
        assert ("name", "battlefield") in ref.zone

    def test_ref_for_is_consistent_with_instance_id(self):
        reg = GameRefsRegistry()
        o = _Obj("bear")
        ref1 = reg.ref_for(o, zone="battlefield")
        ref2 = reg.ref_for(o, zone="battlefield")
        assert ref1.object == ref2.object


class TestZoneEpoch:
    """zone_epoch is the side-effect-free real-transition signal: monotonic,
    advanced only by note_zone_change (i.e. by move_to_zone), and readable
    without minting instance ids."""

    def test_starts_at_zero_and_advances_per_zone_change(self):
        reg = GameRefsRegistry()
        o = _Obj("bear")
        assert reg.zone_epoch(o) == 0
        reg.note_zone_change(o)
        assert reg.zone_epoch(o) == 1
        reg.note_zone_change(o)
        assert reg.zone_epoch(o) == 2

    def test_atomic_round_trip_is_visible(self):
        # A leave-and-return completed between two reads still changes the
        # epoch — the property end-of-window membership checks cannot provide.
        reg = GameRefsRegistry()
        o = _Obj("bear")
        before = reg.zone_epoch(o)
        reg.note_zone_change(o)  # battlefield -> exile (unobserved)
        reg.note_zone_change(o)  # exile -> battlefield (unobserved)
        assert reg.zone_epoch(o) > before

    def test_read_is_side_effect_free(self):
        # Reading the epoch never mints and never perturbs the instance-id
        # sequence: ids minted after many reads equal ids minted without them.
        reg_read = GameRefsRegistry()
        reg_ctrl = GameRefsRegistry()
        o_read, o_ctrl = _Obj("bear"), _Obj("bear")
        for _ in range(5):
            reg_read.zone_epoch(o_read)
        assert reg_read.instance_id(o_read, "battlefield") == reg_ctrl.instance_id(
            o_ctrl, "battlefield"
        )
        # And the read itself is stable (no hidden state advanced).
        assert reg_read.zone_epoch(o_read) == reg_ctrl.zone_epoch(o_ctrl) == 0

    def test_per_object_independence(self):
        reg = GameRefsRegistry()
        a, b = _Obj("a"), _Obj("b")
        reg.note_zone_change(a)
        assert reg.zone_epoch(a) == 1
        assert reg.zone_epoch(b) == 0

    def test_epoch_survives_instance_id_reminting(self):
        # Minting new stint ids (the churn surface) does not touch the epoch.
        reg = GameRefsRegistry()
        o = _Obj("bear")
        reg.note_zone_change(o)
        reg.instance_id(o, "exile")
        reg.instance_id(o, "battlefield")
        assert reg.zone_epoch(o) == 1
