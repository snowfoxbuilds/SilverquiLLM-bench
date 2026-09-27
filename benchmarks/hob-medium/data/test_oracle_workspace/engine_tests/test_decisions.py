"""Unit tests for the Player Decision data layer (engine/decisions.py).

Behavior-driven tests for the Game Symbols vocabulary: PlayerDecision,
DecisionKind, satisfies(), GameRef, ref subset matching, smart constructors,
and the exception hierarchy.
"""

from __future__ import annotations

import pytest

from engine.decisions import (
    Decision,
    DecisionKind,
    GameRef,
    MalformedAttrsError,
    PlayerDecision,
    ref_matches,
    satisfies,
)


class TestSatisfiesTracer:
    def test_general_subset_of_specific_with_same_kind_is_satisfied(self):
        specific = PlayerDecision(
            kind=DecisionKind.OBJECT,
            attrs=frozenset({("color", "R"), ("zone", "battlefield")}),
            modifiers=frozenset(),
        )
        general = PlayerDecision(
            kind=DecisionKind.OBJECT,
            attrs=frozenset({("color", "R")}),
            modifiers=frozenset(),
        )
        assert satisfies(specific, general) is True


class TestSatisfiesSemantics:
    def test_different_kind_never_satisfies(self):
        a = Decision.obj(color="R")
        b = PlayerDecision(kind=DecisionKind.PLAYER, attrs=frozenset({("color", "R")}))
        assert satisfies(a, b) is False

    def test_general_attr_absent_from_specific_is_not_satisfied(self):
        specific = Decision.obj(color="R")
        general = Decision.obj(color="R", zone="battlefield")
        assert satisfies(specific, general) is False

    def test_modifiers_are_invisible_to_satisfies(self):
        restricted_red = Decision.mana(color="R", spend="instant_or_sorcery")
        plain_red = Decision.mana(color="R")
        # The restricted mana (extra Modifier) still satisfies the general red.
        assert satisfies(restricted_red, plain_red) is True

    def test_ref_is_invisible_to_satisfies(self):
        ref = GameRef(object=frozenset({("instance", 7)}))
        with_ref = Decision.obj(ref=ref, color="R")
        without_ref = Decision.obj(color="R")
        assert satisfies(with_ref, without_ref) is True

    def test_number_satisfaction_is_exact_equality(self):
        assert satisfies(Decision.number(3), Decision.number(3)) is True
        assert satisfies(Decision.number(3), Decision.number(4)) is False


class TestSmartConstructors:
    def test_number_builds_number_kind_with_value_attr(self):
        d = Decision.number(3)
        assert d.kind is DecisionKind.NUMBER
        assert d.attrs == frozenset({("value", 3)})
        assert d.ref is None

    def test_yes_and_no_build_bool_values(self):
        assert Decision.yes().kind is DecisionKind.BOOL
        assert Decision.yes().attrs == frozenset({("value", True)})
        assert Decision.no().attrs == frozenset({("value", False)})

    def test_mana_color_is_attr_spend_is_modifier(self):
        d = Decision.mana(color="R", spend="instant_or_sorcery")
        assert d.kind is DecisionKind.MANA
        assert ("color", "R") in d.attrs
        assert ("spend", "instant_or_sorcery") in d.modifiers
        assert ("spend", "instant_or_sorcery") not in d.attrs

    def test_obj_attrs_and_optional_ref(self):
        ref = GameRef(object=frozenset({("instance", 42)}))
        d = Decision.obj(ref=ref, zone="graveyard", color="B")
        assert d.kind is DecisionKind.OBJECT
        assert ("zone", "graveyard") in d.attrs
        assert d.ref is ref

    def test_decisions_are_hashable_and_frozen(self):
        s = {Decision.number(1), Decision.number(1), Decision.number(2)}
        assert len(s) == 2


    def test_color_and_mode_constructors(self):
        assert Decision.color("G").kind is DecisionKind.COLOR
        assert ("color", "G") in Decision.color("G").attrs
        assert satisfies(Decision.color("G"), Decision.color("G")) is True
        assert satisfies(Decision.color("G"), Decision.color("R")) is False
        m = Decision.mode("flicker", index=0)
        assert m.kind is DecisionKind.MODE
        assert ("name", "flicker") in m.attrs


class TestMalformedAttrs:
    def test_unknown_attr_key_for_kind_raises(self):
        with pytest.raises(MalformedAttrsError):
            Decision.obj(bogus_key="x")

    def test_out_of_domain_color_value_raises(self):
        with pytest.raises(MalformedAttrsError):
            Decision.mana(color="purple")

    def test_out_of_domain_zone_value_raises(self):
        with pytest.raises(MalformedAttrsError):
            Decision.obj(zone="nowhere")


class TestSurplusAttrTolerance:
    def test_engine_surplus_attr_does_not_break_satisfies(self):
        # Intent / oracle (general) uses only blessed attrs via the smart
        # constructor; engine (specific) may carry surplus attrs (extra facts
        # the engine knows but the intent never constrains on). The general
        # still subsumes the specific — surplus is inert for matching.
        intent = Decision.obj(color="R")
        engine_specific = PlayerDecision(
            kind=DecisionKind.OBJECT,
            attrs=frozenset({("color", "R"), ("engine_private_fact", "x")}),
        )
        assert satisfies(engine_specific, intent) is True


class TestRefSubsetMatching:
    def test_empty_pattern_matches_any_ref(self):
        # The Baseline Intent pattern (all-empty) matches everything.
        assert ref_matches(GameRef(), GameRef(card=frozenset({("number", "fdn_1")})))

    def test_pattern_field_subset_matches(self):
        pattern = GameRef(card=frozenset({("number", "fdn_123")}))
        actual = GameRef(
            card=frozenset({("number", "fdn_123"), ("set", "fdn")}),
            object=frozenset({("instance", 9)}),
        )
        assert ref_matches(pattern, actual) is True

    def test_pattern_field_not_subset_does_not_match(self):
        pattern = GameRef(card=frozenset({("number", "fdn_999")}))
        actual = GameRef(card=frozenset({("number", "fdn_123")}))
        assert ref_matches(pattern, actual) is False

    def test_object_instance_binding_routes(self):
        pattern = GameRef(object=frozenset({("instance", 7)}))
        assert ref_matches(pattern, GameRef(object=frozenset({("instance", 7)})))
        assert not ref_matches(pattern, GameRef(object=frozenset({("instance", 8)})))
