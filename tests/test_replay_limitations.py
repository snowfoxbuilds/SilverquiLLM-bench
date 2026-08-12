"""Unit tests for the Phase M limitation classifier (total, deterministic).

The classifier assigns every simulate-mode divergence exactly one limitation
tag. These tests pin the taxonomy and prove the classifier is TOTAL — no
divergence type or description shape escapes untagged — and that each tag is
reached by the record shape it is meant to describe. Fixture-backed evidence
that the stream genuinely lacks the distinguishing information for the floor
tags lives in the workspace suite (``engine_tests/test_replay_limitations``).
"""

from __future__ import annotations

from silverquillm.replay.limitations import (
    FLOOR,
    FLOOR_TAGS,
    HIDDEN_PT_CARDS,
    LIMITATION_TAGS,
    LimitationContext,
    classify_limitation,
)


def _rec(dtype, desc, **kw):
    rec = {"type": dtype, "description": desc}
    rec.update(kw)
    return rec


class TestTaxonomy:
    def test_every_tag_wellformed(self):
        for kind, summary in LIMITATION_TAGS.values():
            assert kind in ("floor", "family")
            assert isinstance(summary, str) and summary

    def test_floor_tags_are_a_subset(self):
        assert FLOOR_TAGS <= set(LIMITATION_TAGS)
        assert all(LIMITATION_TAGS[t][0] == FLOOR for t in FLOOR_TAGS)

    def test_floor_tags_are_exactly_the_stream_limits(self):
        assert FLOOR_TAGS == {
            "unfunded-activation",
            "ambiguous-ability",
            "hidden-information",
        }


class TestClassifierTotality:
    def test_every_divergence_type_maps_to_a_known_tag(self):
        # Every DivergenceType value, with an empty-ish description, still lands
        # on a known tag — the classifier never returns None or an alien tag.
        for dtype in (
            "STATE_MISMATCH",
            "ILLEGAL_ACTION",
            "MISSING_CARD",
            "ENGINE_ERROR",
            "REPLAY_INFRA",
            "QUERY_UNANSWERED",
            "PROTOCOL_ERROR",
        ):
            tag = classify_limitation(_rec(dtype, ""), LimitationContext())
            assert tag in LIMITATION_TAGS

    def test_unknown_state_category_still_tagged(self):
        tag = classify_limitation(
            _rec("STATE_MISMATCH", "[future_surface] whatever mismatch: a=1"),
            LimitationContext(),
        )
        assert tag in LIMITATION_TAGS

    def test_classifier_is_deterministic(self):
        rec = _rec("STATE_MISMATCH", "[life_total] Player 2 life mismatch: engine=1, snapshot=2")
        ctx = LimitationContext()
        assert classify_limitation(rec, ctx) == classify_limitation(rec, ctx)


class TestFloorTags:
    def test_cost_could_not_be_paid_is_unfunded(self):
        rec = _rec(
            "ENGINE_ERROR",
            "activate_ability Adventuring Gear (seat 2): AbilityError: "
            "Cannot activate ability — cost could not be paid",
        )
        assert classify_limitation(rec, LimitationContext()) == "unfunded-activation"

    def test_insufficient_mana_is_unfunded(self):
        rec = _rec(
            "ENGINE_ERROR",
            "cast_spell Bite Down (seat 1): CastingError: "
            "Cannot cast 'Bite Down' — insufficient mana",
        )
        assert classify_limitation(rec, LimitationContext()) == "unfunded-activation"

    def test_multiability_source_mismatch_is_ambiguous(self):
        ctx = LimitationContext(ambiguous_sources=frozenset({"Ravenous Amulet"}))
        rec = _rec(
            "STATE_MISMATCH",
            "[tapped_state] Ravenous Amulet tapped state mismatch: "
            "engine=False, snapshot=True",
        )
        assert classify_limitation(rec, ctx) == "ambiguous-ability"

    def test_ambiguous_only_when_source_refused(self):
        # Same record, but the source was NOT refused -> falls to the cadence
        # family, not the ambiguous floor.
        rec = _rec(
            "STATE_MISMATCH",
            "[tapped_state] Ravenous Amulet tapped state mismatch: "
            "engine=False, snapshot=True",
        )
        assert classify_limitation(rec, LimitationContext()) == "resolution-cadence"

    def test_grpid_zero_zone_shell_is_hidden(self):
        rec = _rec(
            "STATE_MISMATCH",
            "[zone_contents] Zone ZoneType_Hand (seat 1) content mismatch: "
            "engine=[0, 93727], snapshot=[93727]",
        )
        assert classify_limitation(rec, LimitationContext()) == "hidden-information"

    def test_library_driven_pt_is_hidden(self):
        assert "Consuming Aberration" in HIDDEN_PT_CARDS
        rec = _rec(
            "STATE_MISMATCH",
            "[power_toughness] Consuming Aberration power mismatch: "
            "engine=16, snapshot=17",
        )
        assert classify_limitation(rec, LimitationContext()) == "hidden-information"

    def test_out_of_set_missing_is_hidden(self):
        rec = _rec(
            "MISSING_CARD",
            "Card '1/1 black green Nightmare (out-of-set grpId 95283)' "
            "(grpId=95283) not implemented in engine",
        )
        assert classify_limitation(rec, LimitationContext()) == "hidden-information"


class TestFamilyTags:
    def test_no_legal_target_is_driving_context(self):
        rec = _rec(
            "ENGINE_ERROR",
            "cast_spell Vampire Soulcaller (seat 2): CastingError: "
            "Cannot cast 'Vampire Soulcaller' — no legal target for 'target'",
        )
        assert classify_limitation(rec, LimitationContext()) == "driving-context"

    def test_sorcery_timing_is_driving_context(self):
        rec = _rec(
            "ENGINE_ERROR",
            "cast_spell Eaten Alive (seat 1): CastingError: "
            "Cannot cast 'Eaten Alive' — sorcery-speed timing not met",
        )
        assert classify_limitation(rec, LimitationContext()) == "driving-context"

    def test_named_token_missing_is_unimplemented(self):
        rec = _rec(
            "MISSING_CARD",
            "Token 'Food token' (grpId=94177) has no engine impl that mints it",
        )
        assert classify_limitation(rec, LimitationContext()) == "unimplemented-effect"

    def test_snapshot_extra_token_is_unimplemented(self):
        ctx = LimitationContext(token_grp_ids=frozenset({94177}))
        rec = _rec(
            "STATE_MISMATCH",
            "[zone_contents] Zone ZoneType_Battlefield (seat 2) content "
            "mismatch: engine=[], snapshot=[94177]",
        )
        assert classify_limitation(rec, ctx) == "unimplemented-effect"

    def test_real_card_zone_offset_is_cadence(self):
        rec = _rec(
            "STATE_MISMATCH",
            "[zone_contents] Zone ZoneType_Battlefield (seat 2) content "
            "mismatch: engine=[93846], snapshot=[]",
        )
        assert classify_limitation(rec, LimitationContext()) == "resolution-cadence"

    def test_engine_extra_token_is_cadence_not_unimplemented(self):
        # Engine minted a token GRE has not yet attested — a timing offset, not
        # an unimplemented minter (which is the snapshot-extra direction).
        ctx = LimitationContext(token_grp_ids=frozenset({94177}))
        rec = _rec(
            "STATE_MISMATCH",
            "[zone_contents] Zone ZoneType_Battlefield (seat 2) content "
            "mismatch: engine=[94177], snapshot=[]",
        )
        assert classify_limitation(rec, ctx) == "resolution-cadence"

    def test_life_and_tapped_and_illegal_are_cadence(self):
        for rec in (
            _rec("STATE_MISMATCH", "[life_total] Player 2 life mismatch: engine=18, snapshot=16"),
            _rec("STATE_MISMATCH", "[tapped_state] Forest tapped state mismatch: engine=True, snapshot=False"),
            _rec("ILLEGAL_ACTION", "[power_toughness] Dauntless Veteran power mismatch: engine=3, snapshot=2",
                 action_card="Dauntless Veteran"),
        ):
            assert classify_limitation(rec, LimitationContext()) == "resolution-cadence"

    def test_replay_infra_tag(self):
        rec = _rec("REPLAY_INFRA", "engine library empty on a GRE-observed draw")
        assert classify_limitation(rec, LimitationContext()) == "replay-infra"
