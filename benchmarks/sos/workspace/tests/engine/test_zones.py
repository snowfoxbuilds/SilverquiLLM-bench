"""Tests for engine/zones.py — zone containers and move_zone logic.

Verifies:
- ZoneContainer: add, remove, contains, get_all, shuffle, top(n), bottom(n).
- Add with position="top" vs position="bottom".
- Remove non-existent object raises ValueError.
- Invalid position raises ValueError.
- Zones.new_player() creates one ZoneContainer per Zone enum member.
- move_zone: round-trip add→move, position="top"/"bottom"/"shuffle".
- move_zone raises IllegalMoveError when object not in source zone.
- Edge case: move object to same zone (no-op).
- Shuffle produces a permutation of the original contents.
- top(n)/bottom(n) slicing correctness and edge cases.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.types import Zone
from benchmarks.sos.workspace.engine.zones import IllegalMoveError, ZoneContainer, Zones, move_zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_objects(n: int) -> list[str]:
    """Create *n* distinct string 'game objects' for testing."""
    return [f"card_{i}" for i in range(n)]


# ---------------------------------------------------------------------------
# ZoneContainer — basic operations
# ---------------------------------------------------------------------------
class TestZoneContainerAdd:
    """Verify ZoneContainer.add with various positions."""

    def test_add_default_position_is_top(self) -> None:
        """Adding without explicit position should append to the top (end)."""
        zc = ZoneContainer()
        zc.add("a")
        zc.add("b")
        assert zc.get_all() == ["a", "b"]

    def test_add_position_top(self) -> None:
        """Explicit position='top' should append to the end."""
        zc = ZoneContainer()
        zc.add("a", position="top")
        zc.add("b", position="top")
        assert zc.get_all() == ["a", "b"]

    def test_add_position_bottom(self) -> None:
        """position='bottom' should insert at index 0 (bottom of zone)."""
        zc = ZoneContainer()
        zc.add("a")
        zc.add("b", position="bottom")
        # "b" was inserted at the bottom, so order should be [b, a]
        assert zc.get_all() == ["b", "a"]

    def test_add_invalid_position_raises(self) -> None:
        """An unsupported position string should raise ValueError."""
        zc = ZoneContainer()
        with pytest.raises(ValueError, match="[Ii]nvalid position"):
            zc.add("a", position="middle")


class TestZoneContainerRemove:
    """Verify ZoneContainer.remove."""

    def test_remove_existing_object(self) -> None:
        """Removing an object that exists should succeed and reduce the list."""
        zc = ZoneContainer()
        zc.add("a")
        zc.add("b")
        zc.remove("a")
        assert not zc.contains("a")
        assert zc.get_all() == ["b"]

    def test_remove_nonexistent_raises(self) -> None:
        """Removing an object not in the zone should raise ValueError."""
        zc = ZoneContainer()
        zc.add("a")
        with pytest.raises(ValueError):
            zc.remove("z")


class TestZoneContainerContains:
    """Verify ZoneContainer.contains."""

    def test_contains_returns_true_for_present_object(self) -> None:
        zc = ZoneContainer()
        zc.add("x")
        assert zc.contains("x") is True

    def test_contains_returns_false_for_absent_object(self) -> None:
        zc = ZoneContainer()
        assert zc.contains("x") is False


class TestZoneContainerGetAll:
    """Verify ZoneContainer.get_all."""

    def test_get_all_returns_ordered_list(self) -> None:
        """get_all should return items in insertion order (bottom→top)."""
        zc = ZoneContainer()
        for item in ["a", "b", "c"]:
            zc.add(item)
        assert zc.get_all() == ["a", "b", "c"]

    def test_get_all_returns_copy(self) -> None:
        """Mutating the returned list should not affect the zone."""
        zc = ZoneContainer()
        zc.add("a")
        result = zc.get_all()
        result.append("intruder")
        assert zc.get_all() == ["a"]

    def test_get_all_empty(self) -> None:
        """Empty zone returns an empty list."""
        zc = ZoneContainer()
        assert zc.get_all() == []


class TestZoneContainerLen:
    """Verify ZoneContainer.__len__."""

    def test_len_reflects_additions(self) -> None:
        zc = ZoneContainer()
        assert len(zc) == 0
        zc.add("a")
        assert len(zc) == 1
        zc.add("b")
        assert len(zc) == 2

    def test_len_reflects_removals(self) -> None:
        zc = ZoneContainer()
        zc.add("a")
        zc.remove("a")
        assert len(zc) == 0


# ---------------------------------------------------------------------------
# ZoneContainer — top / bottom slicing
# ---------------------------------------------------------------------------
class TestZoneContainerTopBottom:
    """Verify top(n) and bottom(n) slicing on ZoneContainer."""

    def _filled_container(self) -> ZoneContainer:
        """Return a ZoneContainer with items ['c0','c1','c2','c3','c4'] (bottom→top)."""
        zc = ZoneContainer()
        for i in range(5):
            zc.add(f"c{i}")
        return zc

    def test_top_returns_last_n_items(self) -> None:
        """top(2) on [c0..c4] should return [c3, c4]."""
        zc = self._filled_container()
        assert zc.top(2) == ["c3", "c4"]

    def test_top_one(self) -> None:
        """top(1) should return only the topmost item."""
        zc = self._filled_container()
        assert zc.top(1) == ["c4"]

    def test_top_all(self) -> None:
        """top(n) where n >= len should return the entire list."""
        zc = self._filled_container()
        assert zc.top(10) == ["c0", "c1", "c2", "c3", "c4"]

    def test_top_zero_returns_empty(self) -> None:
        """top(0) should return an empty list."""
        zc = self._filled_container()
        assert zc.top(0) == []

    def test_top_negative_returns_empty(self) -> None:
        """top with a negative n should return an empty list."""
        zc = self._filled_container()
        assert zc.top(-1) == []

    def test_bottom_returns_first_n_items(self) -> None:
        """bottom(2) on [c0..c4] should return [c0, c1]."""
        zc = self._filled_container()
        assert zc.bottom(2) == ["c0", "c1"]

    def test_bottom_one(self) -> None:
        """bottom(1) should return only the bottommost item."""
        zc = self._filled_container()
        assert zc.bottom(1) == ["c0"]

    def test_bottom_all(self) -> None:
        """bottom(n) where n >= len should return the entire list."""
        zc = self._filled_container()
        assert zc.bottom(10) == ["c0", "c1", "c2", "c3", "c4"]

    def test_bottom_zero_returns_empty(self) -> None:
        """bottom(0) should return an empty list."""
        zc = self._filled_container()
        assert zc.bottom(0) == []

    def test_bottom_negative_returns_empty(self) -> None:
        """bottom with a negative n should return an empty list."""
        zc = self._filled_container()
        assert zc.bottom(-1) == []


# ---------------------------------------------------------------------------
# ZoneContainer — shuffle
# ---------------------------------------------------------------------------
class TestZoneContainerShuffle:
    """Verify ZoneContainer.shuffle produces a permutation."""

    def test_shuffle_preserves_all_elements(self) -> None:
        """After shuffle, the zone should contain the same set of objects."""
        zc = ZoneContainer()
        objs = _make_objects(20)
        for o in objs:
            zc.add(o)
        zc.shuffle()
        assert sorted(zc.get_all()) == sorted(objs)

    def test_shuffle_changes_order(self) -> None:
        """With enough elements, shuffle should produce a different order.

        We retry a few times to avoid a vanishingly-unlikely identical shuffle.
        """
        zc = ZoneContainer()
        objs = _make_objects(50)
        for o in objs:
            zc.add(o)
        original = list(objs)
        changed = False
        for _ in range(5):
            zc.shuffle()
            if zc.get_all() != original:
                changed = True
                break
        assert changed, "shuffle did not change order after 5 attempts with 50 elements"

    def test_shuffle_single_element_no_error(self) -> None:
        """Shuffling a single-element zone should not raise."""
        zc = ZoneContainer()
        zc.add("only")
        zc.shuffle()
        assert zc.get_all() == ["only"]


# ---------------------------------------------------------------------------
# Zones — per-player zone collection
# ---------------------------------------------------------------------------
class TestZonesNewPlayer:
    """Verify Zones.new_player factory."""

    def test_new_player_creates_all_zones(self) -> None:
        """Every Zone enum member should be present in a freshly created Zones."""
        zones = Zones.new_player()
        for zone in Zone:
            assert zone in zones, f"Zone {zone} missing from Zones.new_player()"

    def test_new_player_zones_are_empty(self) -> None:
        """Every zone in a new player should start empty."""
        zones = Zones.new_player()
        for zone in Zone:
            assert len(zones[zone]) == 0

    def test_new_player_zones_are_zone_containers(self) -> None:
        """Each value should be a ZoneContainer instance."""
        zones = Zones.new_player()
        for zone in Zone:
            assert isinstance(zones[zone], ZoneContainer)

    def test_zones_subscript_access(self) -> None:
        """zones[Zone.LIBRARY] should return the library ZoneContainer."""
        zones = Zones.new_player()
        lib = zones[Zone.LIBRARY]
        lib.add("card_a")
        assert zones[Zone.LIBRARY].contains("card_a")


# ---------------------------------------------------------------------------
# move_zone — round-trip and positions
# ---------------------------------------------------------------------------
class TestMoveZone:
    """Verify move_zone transfers objects between ZoneContainers."""

    def test_move_basic_round_trip(self) -> None:
        """Add to zone A, move to zone B — verify A empty, B contains object."""
        src = ZoneContainer()
        dst = ZoneContainer()
        src.add("card")
        move_zone("card", src, dst)
        assert not src.contains("card")
        assert dst.contains("card")

    def test_move_position_top(self) -> None:
        """move_zone with position='top' places item at the top of destination."""
        src = ZoneContainer()
        dst = ZoneContainer()
        dst.add("existing")
        src.add("newcomer")
        move_zone("newcomer", src, dst, position="top")
        assert dst.top(1) == ["newcomer"]

    def test_move_position_bottom(self) -> None:
        """move_zone with position='bottom' places item at bottom of destination."""
        src = ZoneContainer()
        dst = ZoneContainer()
        dst.add("existing")
        src.add("newcomer")
        move_zone("newcomer", src, dst, position="bottom")
        assert dst.bottom(1) == ["newcomer"]

    def test_move_position_shuffle(self) -> None:
        """move_zone with position='shuffle' adds then shuffles the destination.

        We verify the object is present in the destination and that it contains
        all original elements plus the new one (a permutation).
        """
        src = ZoneContainer()
        dst = ZoneContainer()
        for i in range(20):
            dst.add(f"lib_{i}")
        src.add("new_card")
        expected_contents = sorted([f"lib_{i}" for i in range(20)] + ["new_card"])

        move_zone("new_card", src, dst, position="shuffle")
        assert not src.contains("new_card")
        assert dst.contains("new_card")
        assert sorted(dst.get_all()) == expected_contents

    def test_move_removes_from_source(self) -> None:
        """After move, the source should no longer contain the object."""
        src = ZoneContainer()
        src.add("a")
        src.add("b")
        dst = ZoneContainer()
        move_zone("a", src, dst)
        assert src.get_all() == ["b"]


class TestMoveZoneErrors:
    """Verify move_zone error conditions."""

    def test_move_object_not_in_source_raises_illegal_move(self) -> None:
        """Moving an object not in the source zone should raise IllegalMoveError."""
        src = ZoneContainer()
        dst = ZoneContainer()
        with pytest.raises(IllegalMoveError):
            move_zone("ghost", src, dst)

    def test_illegal_move_error_is_an_exception(self) -> None:
        """IllegalMoveError should be a subclass of Exception."""
        assert issubclass(IllegalMoveError, Exception)


class TestMoveZoneSameZoneNoOp:
    """Edge case: moving an object from a zone to the same zone is a no-op."""

    def test_same_zone_noop_preserves_contents(self) -> None:
        """If from_zone is to_zone, contents should be unchanged."""
        zc = ZoneContainer()
        zc.add("card_a")
        zc.add("card_b")
        original = zc.get_all()
        move_zone("card_a", zc, zc, position="top")
        assert zc.get_all() == original

    def test_same_zone_noop_does_not_remove(self) -> None:
        """The object should still be present after a same-zone move."""
        zc = ZoneContainer()
        zc.add("card_a")
        move_zone("card_a", zc, zc)
        assert zc.contains("card_a")


# ---------------------------------------------------------------------------
# Integration-style: Zones + move_zone
# ---------------------------------------------------------------------------
class TestZonesMoveZoneIntegration:
    """Use Zones.new_player() containers with move_zone for realistic scenarios."""

    def test_move_from_library_to_hand(self) -> None:
        """Simulate drawing a card: library → hand."""
        zones = Zones.new_player()
        zones[Zone.LIBRARY].add("draw_me")
        move_zone("draw_me", zones[Zone.LIBRARY], zones[Zone.HAND])
        assert not zones[Zone.LIBRARY].contains("draw_me")
        assert zones[Zone.HAND].contains("draw_me")

    def test_move_from_hand_to_battlefield(self) -> None:
        """Simulate playing a card: hand → battlefield."""
        zones = Zones.new_player()
        zones[Zone.HAND].add("my_creature")
        move_zone("my_creature", zones[Zone.HAND], zones[Zone.BATTLEFIELD])
        assert zones[Zone.BATTLEFIELD].contains("my_creature")
        assert not zones[Zone.HAND].contains("my_creature")

    def test_move_from_battlefield_to_graveyard(self) -> None:
        """Simulate destruction: battlefield → graveyard."""
        zones = Zones.new_player()
        zones[Zone.BATTLEFIELD].add("doomed")
        move_zone("doomed", zones[Zone.BATTLEFIELD], zones[Zone.GRAVEYARD])
        assert zones[Zone.GRAVEYARD].contains("doomed")
        assert not zones[Zone.BATTLEFIELD].contains("doomed")

    def test_shuffle_into_library(self) -> None:
        """Simulate tutoring: hand → library with shuffle."""
        zones = Zones.new_player()
        for i in range(10):
            zones[Zone.LIBRARY].add(f"lib_{i}")
        zones[Zone.HAND].add("tutor_target")
        move_zone(
            "tutor_target",
            zones[Zone.HAND],
            zones[Zone.LIBRARY],
            position="shuffle",
        )
        assert zones[Zone.LIBRARY].contains("tutor_target")
        assert len(zones[Zone.LIBRARY]) == 11
