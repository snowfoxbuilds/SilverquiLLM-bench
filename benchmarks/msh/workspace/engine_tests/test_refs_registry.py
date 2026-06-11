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
