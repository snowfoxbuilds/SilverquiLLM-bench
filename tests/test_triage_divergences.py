"""Tests for scripts/triage_divergences.py and the report attribution fields.

Pins the two contracts issue #40's Tier 0 rests on:

* the serializer (``silverquillm.replay.cli._aggregate_reports``) emits the
  original four-key divergence records in observer mode — byte-identical
  legacy shape — and adds exactly the four attribution fields in simulate
  mode;
* the triage tool's cluster partition is total (every record in exactly one
  cluster, sums reconcile), its message-template parsers understand every
  divergence description format the pipeline produces, and its output is
  deterministic.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from silverquillm.replay.cli import _aggregate_reports
from silverquillm.replay.types import ReplayAction
from silverquillm.replay.validation import (
    Divergence,
    DivergenceType,
    ValidationReport,
)

# ---------------------------------------------------------------------------
# Import the script module via importlib (scripts/ is not a package)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = REPO_ROOT / "scripts" / "triage_divergences.py"

_spec = importlib.util.spec_from_file_location("triage_divergences", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["triage_divergences"] = _mod
_spec.loader.exec_module(_mod)

bucket_of = _mod.bucket_of
build_name_resolver = _mod.build_name_resolver
build_triage = _mod.build_triage
cluster_key = _mod.cluster_key
parse_engine_error = _mod.parse_engine_error
parse_life = _mod.parse_life
parse_missing = _mod.parse_missing
parse_pt = _mod.parse_pt
parse_tapped = _mod.parse_tapped
parse_zone = _mod.parse_zone
render_markdown = _mod.render_markdown


def _record(
    desc: str,
    dtype: str = "STATE_MISMATCH",
    gsid: int = 10,
    game: str | None = None,
    **extra,
) -> dict:
    rec = {
        "game_state_id": gsid,
        "type": dtype,
        "description": desc,
        "involved_grp_ids": [],
    }
    if game is not None:
        rec.update(
            {"game": game, "turn_number": 3, "action_type": None, "action_card": None}
        )
    rec.update(extra)
    return rec


_NAME_OF = build_name_resolver(
    {"grpId_to_card": {"93855": {"card_name": "Llanowar Elves"}}},
    {
        "tokens": {"94177": {"label": "Food token"}},
        "arena_only_cards": {"93937": {"resolves_to": "Gnarlid Colony"}},
    },
)


# ---------------------------------------------------------------------------
# Bucketing (issue #40 counted-once convention)
# ---------------------------------------------------------------------------


class TestBucketOf:
    def test_state_mismatch_by_category(self):
        assert bucket_of(_record("[zone_contents] Zone X (seat 1) ...")) == "zone_contents"
        assert bucket_of(_record("[power_toughness] X power mismatch: ...")) == "power_toughness"
        assert bucket_of(_record("[life_total] Player 1 ...")) == "life_total"
        assert bucket_of(_record("[tapped_state] X ...")) == "tapped_state"

    def test_illegal_action_stays_operational_despite_bracket_prefix(self):
        # The deliberate divergence from TestGoldenGame._fingerprint: the
        # issue's bucket table counts ILLEGAL_ACTION by type even though its
        # descriptions carry state-mismatch [category] prefixes.
        rec = _record(
            "[zone_contents] Zone ZoneType_Graveyard (seat 2) content mismatch: "
            "engine=[93940, 93940], snapshot=[93940]",
            dtype="ILLEGAL_ACTION",
        )
        assert bucket_of(rec) == "ILLEGAL_ACTION"

    def test_operational_types_by_type(self):
        for dtype in ("ENGINE_ERROR", "MISSING_CARD", "REPLAY_INFRA"):
            assert bucket_of(_record("anything", dtype=dtype)) == dtype

    def test_unbracketed_state_mismatch_falls_back_to_type(self):
        assert bucket_of(_record("no bracket prefix")) == "STATE_MISMATCH"


# ---------------------------------------------------------------------------
# Message-template parsers — one per pipeline format
# ---------------------------------------------------------------------------


class TestParsers:
    def test_zone_with_duplicate_grp_ids_is_multiset(self):
        parsed = parse_zone(
            "[zone_contents] Zone ZoneType_Graveyard (seat 2) content mismatch: "
            "engine=[93940, 93940], snapshot=[93940]"
        )
        assert parsed == {
            "zone": "ZoneType_Graveyard",
            "seat": 2,
            "engine": [93940, 93940],
            "snapshot": [93940],
        }
        key = cluster_key(_record(
            "[zone_contents] Zone ZoneType_Graveyard (seat 2) content mismatch: "
            "engine=[93940, 93940], snapshot=[93940]"
        ), _NAME_OF)
        # The duplicate survives the diff: engine has one extra 93940.
        assert key == ("zone_contents", "ZoneType_Graveyard", "engine_extra", "grpId_93940")

    def test_zone_empty_list(self):
        parsed = parse_zone(
            "[zone_contents] Zone ZoneType_Battlefield (seat 1) content mismatch: "
            "engine=[], snapshot=[93855, 95192]"
        )
        assert parsed["engine"] == []
        assert parsed["snapshot"] == [93855, 95192]

    def test_power_and_toughness_records(self):
        power = parse_pt("[power_toughness] Llanowar Elves power mismatch: engine=1, snapshot=2")
        tough = parse_pt("[power_toughness] Llanowar Elves toughness mismatch: engine=-1, snapshot=0")
        assert power == {"card": "Llanowar Elves", "dimension": "power", "engine": 1, "snapshot": 2}
        assert tough["dimension"] == "toughness"
        assert tough["engine"] == -1

    def test_life(self):
        parsed = parse_life("[life_total] Player 2 life mismatch: engine=18, snapshot=16")
        assert parsed == {"seat": 2, "engine": 18, "snapshot": 16}

    def test_tapped(self):
        parsed = parse_tapped(
            "[tapped_state] Hare Apparent tapped state mismatch: engine=False, snapshot=True"
        )
        assert parsed == {"card": "Hare Apparent", "engine": False, "snapshot": True}

    def test_engine_error_full_template(self):
        parsed = parse_engine_error(
            "activate_ability Goldvein Pick (seat 2): AbilityError: "
            "Cannot activate ability — cost could not be paid"
        )
        assert (parsed["verb"], parsed["card"], parsed["exc"]) == (
            "activate_ability",
            "Goldvein Pick",
            "AbilityError",
        )

    def test_engine_error_zone_context_template(self):
        parsed = parse_engine_error(
            "move_to_zone Fake Card (ZoneType_Hand->ZoneType_Battlefield): KeyError: 'x'"
        )
        assert (parsed["verb"], parsed["card"], parsed["ctx"]) == (
            "move_to_zone",
            "Fake Card",
            "ZoneType_Hand->ZoneType_Battlefield",
        )

    def test_engine_error_no_subject_template(self):
        parsed = parse_engine_error("draw_card (seat 2): EngineError: library empty")
        assert (parsed["verb"], parsed["card"]) == ("draw_card", "")

    def test_engine_error_no_context_template(self):
        parsed = parse_engine_error(
            "play_land Forest: CastingError: Cannot play land 'Forest' — no land plays remaining"
        )
        assert (parsed["verb"], parsed["card"], parsed["exc"]) == (
            "play_land",
            "Forest",
            "CastingError",
        )

    def test_engine_error_bare_step_template(self):
        parsed = parse_engine_error("declare_attackers_step: TypeError: boom")
        assert (parsed["verb"], parsed["card"], parsed["exc"]) == (
            "declare_attackers_step",
            "",
            "TypeError",
        )

    def test_engine_error_raised_and_parse_error_templates(self):
        assert parse_engine_error("Engine raised ValueError: bad")["verb"] == "raise"
        assert parse_engine_error("Parse error: truncated")["verb"] == "parse_error"

    def test_missing_card_and_token(self):
        card = parse_missing("Card 'Llanowar Elves' (grpId=93855) not implemented in engine")
        token = parse_missing(
            "Token 'Treasure token' (grpId=94178) has no engine impl that mints it"
        )
        assert (card["kind"], card["identity"], card["grp_id"]) == ("Card", "Llanowar Elves", 93855)
        assert (token["kind"], token["identity"]) == ("Token", "Treasure token")


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------


class TestNameResolver:
    def test_card_map_wins(self):
        assert _NAME_OF(93855) == "Llanowar Elves"

    def test_token_label(self):
        assert _NAME_OF(94177) == "Food token"

    def test_arena_only(self):
        assert _NAME_OF(93937) == "Gnarlid Colony (arena-only)"

    def test_fallback(self):
        assert _NAME_OF(11111) == "grpId_11111"

    def test_missing_maps_entirely(self):
        name_of = build_name_resolver(None, None)
        assert name_of(93855) == "grpId_93855"


# ---------------------------------------------------------------------------
# Cluster keys
# ---------------------------------------------------------------------------


class TestClusterKeys:
    def test_life_delta_cap_and_sign(self):
        low = cluster_key(
            _record("[life_total] Player 2 life mismatch: engine=10, snapshot=12"), _NAME_OF
        )
        capped = cluster_key(
            _record("[life_total] Player 1 life mismatch: engine=20, snapshot=2"), _NAME_OF
        )
        assert low == ("life_total", "seat 2", "engine_low", "delta 2")
        assert capped == ("life_total", "seat 1", "engine_high", "delta 6+")

    def test_zone_both_directions(self):
        key = cluster_key(
            _record(
                "[zone_contents] Zone ZoneType_Battlefield (seat 1) content mismatch: "
                "engine=[93855], snapshot=[94177]"
            ),
            _NAME_OF,
        )
        assert key == (
            "zone_contents",
            "ZoneType_Battlefield",
            "both",
            "engine+{Llanowar Elves}|snapshot+{Food token}",
        )

    def test_zone_signature_merges_multiplicities(self):
        one = cluster_key(
            _record(
                "[zone_contents] Zone ZoneType_Battlefield (seat 1) content mismatch: "
                "engine=[], snapshot=[94177]"
            ),
            _NAME_OF,
        )
        three = cluster_key(
            _record(
                "[zone_contents] Zone ZoneType_Battlefield (seat 1) content mismatch: "
                "engine=[], snapshot=[94177, 94177, 94177]"
            ),
            _NAME_OF,
        )
        assert one == three == (
            "zone_contents",
            "ZoneType_Battlefield",
            "snapshot_extra",
            "Food token",
        )

    def test_illegal_action_uses_attribution_fields(self):
        rec = _record(
            "[zone_contents] Zone ZoneType_Graveyard (seat 2) content mismatch: "
            "engine=[93940, 93940], snapshot=[93940]",
            dtype="ILLEGAL_ACTION",
            game="d/match0_game0.json",
            action_type="spell_cast",
            action_card="Bite Down",
        )
        assert cluster_key(rec, _NAME_OF) == (
            "ILLEGAL_ACTION",
            "zone_contents",
            "spell_cast",
            "Bite Down",
        )

    def test_replay_infra_digits_normalized(self):
        a = cluster_key(_record("draw (seat 2): engine library empty", dtype="REPLAY_INFRA"), _NAME_OF)
        b = cluster_key(_record("draw (seat 1): engine library empty", dtype="REPLAY_INFRA"), _NAME_OF)
        assert a == b == ("REPLAY_INFRA", "draw (seat N): engine library empty")

    def test_unknown_shape_lands_in_unparsed_never_dropped(self):
        key = cluster_key(_record("weird text", dtype="ENGINE_ERROR"), _NAME_OF)
        assert key[1] == "UNPARSED"


# ---------------------------------------------------------------------------
# Partition + reconciliation
# ---------------------------------------------------------------------------


def _synthetic_report() -> dict:
    game = "draft/match0_game0.json"
    return {
        "total_divergences": 6,
        "divergences": [
            # One P/T divergence = two records, same cluster, counted twice.
            _record("[power_toughness] Llanowar Elves power mismatch: engine=1, snapshot=2", game=game),
            _record("[power_toughness] Llanowar Elves toughness mismatch: engine=1, snapshot=2", game=game),
            _record("[life_total] Player 1 life mismatch: engine=20, snapshot=19", game=game, gsid=11),
            _record(
                "activate_ability Goldvein Pick (seat 2): AbilityError: cost could not be paid",
                dtype="ENGINE_ERROR",
                game=game,
                gsid=12,
            ),
            _record(
                "Token 'Food token' (grpId=94177) has no engine impl that mints it",
                dtype="MISSING_CARD",
                game=game,
                gsid=13,
            ),
            _record("???", dtype="ENGINE_ERROR", game=game, gsid=14),
        ],
    }


class TestBuildTriage:
    def test_partition_is_exact_and_counted_once(self):
        triage = build_triage(_synthetic_report(), _NAME_OF)
        recon = triage["reconciliation"]
        assert recon["exact"] is True
        assert recon["records"] == recon["clusters_sum"] == 6
        pt = next(c for c in triage["clusters"] if c["bucket"] == "power_toughness")
        # Two records (power + toughness), one cluster — records counted once.
        assert pt["count"] == 2
        assert pt["metadata"]["by_dimension"] == {"power": 1, "toughness": 1}

    def test_unparsed_counted_and_flagged(self):
        triage = build_triage(_synthetic_report(), _NAME_OF)
        assert triage["reconciliation"]["unparsed_records"] == 1
        unparsed = [c for c in triage["clusters"] if c["unparsed"]]
        assert len(unparsed) == 1 and unparsed[0]["count"] == 1

    def test_total_divergences_mismatch_breaks_exactness(self):
        report = _synthetic_report()
        report["total_divergences"] = 7  # lies about its own record count
        triage = build_triage(report, _NAME_OF)
        assert triage["reconciliation"]["exact"] is False

    def test_deterministic_output(self):
        a = build_triage(_synthetic_report(), _NAME_OF)
        b = build_triage(_synthetic_report(), _NAME_OF)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert render_markdown(a, 200) == render_markdown(b, 200)

    def test_legacy_report_without_attribution_still_clusters(self):
        report = _synthetic_report()
        for rec in report["divergences"]:
            for key in ("game", "turn_number", "action_type", "action_card"):
                rec.pop(key, None)
        triage = build_triage(report, _NAME_OF)
        assert triage["attribution_available"] is False
        assert triage["reconciliation"]["exact"] is True
        # ILLEGAL/zone clustering keys degrade to "?" fields, never crash.
        assert all(c["top_games"] == {"unknown": c["count"]} for c in triage["clusters"])


# ---------------------------------------------------------------------------
# Serializer: observer byte-identity + simulate attribution fields
# ---------------------------------------------------------------------------


def _make_report() -> ValidationReport:
    action = ReplayAction(
        action_type="spell_cast",
        turn_number=4,
        player_seat_id=2,
        card_name="Bite Down",
        grp_id=93905,
    )
    return ValidationReport(
        total_snapshots=5,
        successful_comparisons=3,
        divergences=[
            Divergence(
                game_state_id=9,
                divergence_type=DivergenceType.STATE_MISMATCH,
                description="[life_total] Player 2 life mismatch: engine=18, snapshot=16",
                action=action,
                involved_grp_ids=[93905],
            ),
            Divergence(
                game_state_id=12,
                divergence_type=DivergenceType.ENGINE_ERROR,
                description="Engine raised ValueError: bad",
                involved_grp_ids=[],
            ),
        ],
        source="draft/match0_game0.json",
    )


class TestAggregateReportsSerializer:
    def test_observer_records_keep_exact_legacy_shape(self):
        summary = _aggregate_reports([_make_report()], {}, simulate=False)
        assert summary["divergences"] == [
            {
                "game_state_id": 9,
                "type": "STATE_MISMATCH",
                "description": "[life_total] Player 2 life mismatch: engine=18, snapshot=16",
                "involved_grp_ids": [93905],
            },
            {
                "game_state_id": 12,
                "type": "ENGINE_ERROR",
                "description": "Engine raised ValueError: bad",
                "involved_grp_ids": [],
            },
        ]

    def test_observer_default_matches_explicit_false(self):
        assert _aggregate_reports([_make_report()], {}) == _aggregate_reports(
            [_make_report()], {}, simulate=False
        )

    def test_simulate_adds_exactly_the_attribution_fields(self):
        summary = _aggregate_reports([_make_report()], {}, simulate=True)
        first, second = summary["divergences"]
        assert first == {
            "game_state_id": 9,
            "type": "STATE_MISMATCH",
            "description": "[life_total] Player 2 life mismatch: engine=18, snapshot=16",
            "involved_grp_ids": [93905],
            "game": "draft/match0_game0.json",
            "turn_number": 4,
            "action_type": "spell_cast",
            "action_card": "Bite Down",
        }
        # No action attached → attribution fields degrade to None, key set identical.
        assert second["game"] == "draft/match0_game0.json"
        assert second["turn_number"] is None
        assert second["action_type"] is None
        assert second["action_card"] is None
        assert set(first) == set(second)

    def test_missing_source_degrades_to_none(self):
        report = _make_report()
        report.source = ""
        summary = _aggregate_reports([report], {}, simulate=True)
        assert summary["divergences"][0]["game"] is None
