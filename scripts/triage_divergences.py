#!/usr/bin/env python3
"""Cluster replay-validation divergences per root cause (issue #40 Tier 0).

Consumes the JSON report written by ``benchmark validate ... --simulate
--report <path>`` and partitions EVERY divergence record into exactly one
deterministic root-cause cluster, so the state-mismatch buckets that were
never decomposed (zone_contents, power_toughness, life_total, tapped_state,
ILLEGAL_ACTION) become a ranked, evidence-backed worklist. The cluster table
is the input to classifying each cluster as engine gap / card gap /
executor-reconstruction gap / stream limitation.

Usage::

    python scripts/triage_divergences.py REPORT.json \
        [--corpus /mnt/data/benchmark-replays/fdn] \
        [--out-dir benchmarks/msh/analysis] [--top 40] \
        [--md-rows 200] [--no-slices]

Outputs ``triage_<report-stem>.json`` (machine artifact: ranked clusters,
reconciliation block, zone-card involvement index) and
``triage_<report-stem>.md`` (human table) into the gitignored analysis dir.
Both are deterministic: re-running over the same report reproduces them
byte-identically (no timestamps; every collection is sorted).

Counting convention (issue #40, "counted-once"): STATE_MISMATCH records are
bucketed by their leading ``[category]``; the operational types
(ENGINE_ERROR, ILLEGAL_ACTION, MISSING_CARD, REPLAY_INFRA, ...) are bucketed
by type. Note this deliberately differs from ``TestGoldenGame._fingerprint``
(engine_tests/test_replay_simulate.py), whose ``by_category`` folds
ILLEGAL_ACTION records into the state categories because their descriptions
also carry ``[category]`` prefixes.

Guarantees:

* every record is assigned to exactly one cluster (``cluster_key`` is a
  total function; records no parser understands land in a loud ``UNPARSED``
  cluster, never dropped);
* cluster counts sum to the record count and to the report's
  ``total_divergences``, per bucket and overall — any mismatch is a hard
  failure (exit 1);
* ``UNPARSED`` records present → exit 3 after writing outputs (the corpus
  report is expected to parse completely; synthetic/legacy inputs may not).

Reports produced before the simulate-gated attribution fields (``game``,
``turn_number``, ``action_type``, ``action_card``) still cluster fine;
game attribution and transcript slices are then skipped with an explicit
note. ``involved_grp_ids`` is never used as a clustering signal — for
STATE_MISMATCH it holds the snapshot's co-occurring action grpIds, not the
mismatching object.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CORPUS = Path("/mnt/data/benchmark-replays/fdn")
REPO_ROOT = Path(__file__).resolve().parent.parent
CARD_ID_MAP_PATH = REPO_ROOT / "data" / "replays" / "card_id_map.json"
TOKEN_ID_MAP_PATH = REPO_ROOT / "data" / "replays" / "token_id_map.json"
DEFAULT_OUT_DIR = REPO_ROOT / "benchmarks" / "msh" / "analysis"

CONVENTION = "issue40-counted-once"

# Phase M limitation taxonomy — imported from the shared classifier so the
# triage reconciliation validates against the same tag set the serializer
# emits. Falls back to an empty set when the package is not importable (the
# script still clusters; only the tag-reconciliation completeness check needs
# it), so a bare-script invocation never crashes.
try:
    from silverquillm.replay.limitations import FLOOR_TAGS, LIMITATION_TAGS

    _KNOWN_LIMITATION_TAGS = frozenset(LIMITATION_TAGS)
    _FLOOR_LIMITATION_TAGS = frozenset(FLOOR_TAGS)
except Exception:  # noqa: BLE001 — standalone invocation without the package
    _KNOWN_LIMITATION_TAGS = frozenset()
    _FLOOR_LIMITATION_TAGS = frozenset()

# Records with any other type are bucketed by type (operational buckets).
STATE_MISMATCH_TYPE = "STATE_MISMATCH"

# How many snapshots either side of a divergence a transcript slice covers.
SLICE_RADIUS = 2
# Exemplars retained per cluster (one per distinct game where possible).
MAX_EXEMPLARS = 3
# life_total |delta| values are capped here to bound the cluster count.
LIFE_DELTA_CAP = 6

# ---------------------------------------------------------------------------
# Message-template parsers
# ---------------------------------------------------------------------------

_RE_ZONE = re.compile(
    r"^\[zone_contents\] Zone (?P<zone>\S+) \(seat (?P<seat>\d+)\) content "
    r"mismatch: engine=\[(?P<engine>[^\]]*)\], snapshot=\[(?P<snap>[^\]]*)\]$"
)
_RE_PT = re.compile(
    r"^\[power_toughness\] (?P<card>.+) (?P<dim>power|toughness) mismatch: "
    r"engine=(?P<engine>-?\d+), snapshot=(?P<snap>-?\d+)$"
)
_RE_LIFE = re.compile(
    r"^\[life_total\] Player (?P<seat>\d+) life mismatch: "
    r"engine=(?P<engine>-?\d+), snapshot=(?P<snap>-?\d+)$"
)
_RE_TAPPED = re.compile(
    r"^\[tapped_state\] (?P<card>.+) tapped state mismatch: "
    r"engine=(?P<engine>True|False), snapshot=(?P<snap>True|False)$"
)
_RE_MISSING = re.compile(
    r"^(?P<kind>Card|Token) '(?P<identity>.+)' \(grpId=(?P<grp>\d+)\)"
)
# "cast_spell Burst Lightning (seat 2): CastingError: ..." — verb, subject,
# parenthesized context, exception. Subject is minimal so the FIRST " (...):"
# closes it (FDN card names contain no parentheses).
_RE_ENGINE_FULL = re.compile(
    r"^(?P<verb>\w+) (?P<card>.+?) \((?P<ctx>[^)]*)\): "
    r"(?P<exc>\w+): (?P<msg>.*)$",
    re.DOTALL,
)
# "draw_card (seat 2): ...": verb + context, no subject.
_RE_ENGINE_CTX = re.compile(
    r"^(?P<verb>\w+) \((?P<ctx>[^)]*)\): (?P<exc>\w+): (?P<msg>.*)$", re.DOTALL
)
# "play_land Forest: ...": verb + subject, no parenthesized context.
_RE_ENGINE_NOCTX = re.compile(
    r"^(?P<verb>\w+) (?P<card>[^:(]+?): (?P<exc>\w+): (?P<msg>.*)$", re.DOTALL
)
# "declare_attackers_step: ...": bare verb.
_RE_ENGINE_BARE = re.compile(r"^(?P<verb>\w+): (?P<exc>\w+): (?P<msg>.*)$", re.DOTALL)
_RE_ENGINE_RAISED = re.compile(r"^Engine raised (?P<exc>\w+): (?P<msg>.*)$", re.DOTALL)
_RE_PARSE_ERROR = re.compile(r"^Parse error: ", re.DOTALL)


def _int_list(text: str) -> list[int]:
    return [int(tok) for tok in text.split(",") if tok.strip()]


def parse_zone(desc: str) -> dict[str, Any] | None:
    m = _RE_ZONE.match(desc)
    if not m:
        return None
    return {
        "zone": m["zone"],
        "seat": int(m["seat"]),
        "engine": _int_list(m["engine"]),
        "snapshot": _int_list(m["snap"]),
    }


def parse_pt(desc: str) -> dict[str, Any] | None:
    m = _RE_PT.match(desc)
    if not m:
        return None
    return {
        "card": m["card"],
        "dimension": m["dim"],
        "engine": int(m["engine"]),
        "snapshot": int(m["snap"]),
    }


def parse_life(desc: str) -> dict[str, Any] | None:
    m = _RE_LIFE.match(desc)
    if not m:
        return None
    return {"seat": int(m["seat"]), "engine": int(m["engine"]), "snapshot": int(m["snap"])}


def parse_tapped(desc: str) -> dict[str, Any] | None:
    m = _RE_TAPPED.match(desc)
    if not m:
        return None
    return {"card": m["card"], "engine": m["engine"] == "True", "snapshot": m["snap"] == "True"}


def parse_missing(desc: str) -> dict[str, Any] | None:
    m = _RE_MISSING.match(desc)
    if not m:
        return None
    return {"kind": m["kind"], "identity": m["identity"], "grp_id": int(m["grp"])}


def parse_engine_error(desc: str) -> dict[str, Any] | None:
    m = _RE_ENGINE_FULL.match(desc)
    if m:
        return {"verb": m["verb"], "card": m["card"], "ctx": m["ctx"], "exc": m["exc"], "msg": m["msg"]}
    m = _RE_ENGINE_CTX.match(desc)
    if m:
        return {"verb": m["verb"], "card": "", "ctx": m["ctx"], "exc": m["exc"], "msg": m["msg"]}
    m = _RE_ENGINE_RAISED.match(desc)
    if m:
        return {"verb": "raise", "card": "", "ctx": "", "exc": m["exc"], "msg": m["msg"]}
    m = _RE_ENGINE_NOCTX.match(desc)
    if m:
        return {"verb": m["verb"], "card": m["card"], "ctx": "", "exc": m["exc"], "msg": m["msg"]}
    m = _RE_ENGINE_BARE.match(desc)
    if m:
        return {"verb": m["verb"], "card": "", "ctx": "", "exc": m["exc"], "msg": m["msg"]}
    if _RE_PARSE_ERROR.match(desc):
        return {"verb": "parse_error", "card": "", "ctx": "", "exc": "", "msg": desc}
    return None


# ---------------------------------------------------------------------------
# Bucketing and identity resolution
# ---------------------------------------------------------------------------


def bucket_of(record: dict[str, Any]) -> str:
    """Issue #40 counted-once bucket for one serialized divergence record.

    STATE_MISMATCH by leading ``[category]``; every other type (the
    operational buckets) by type — including ILLEGAL_ACTION, whose
    descriptions also carry a ``[category]`` prefix.
    """
    if record["type"] == STATE_MISMATCH_TYPE:
        desc = record["description"]
        if desc.startswith("[") and "]" in desc:
            return desc[1 : desc.index("]")]
    return record["type"]


def build_name_resolver(
    card_id_map: dict[str, Any] | None,
    token_id_map: dict[str, Any] | None,
) -> Callable[[int], str]:
    """Map a grpId to a stable display name.

    Priority: real card (card_id_map) → token identity (token_id_map
    ``label``) → arena-only resolution → ``grpId_<n>`` fallback.
    """
    grp_to_card = (card_id_map or {}).get("grpId_to_card", {})
    tokens = (token_id_map or {}).get("tokens", {})
    arena_only = (token_id_map or {}).get("arena_only_cards", {})

    def name_of(grp_id: int) -> str:
        key = str(grp_id)
        card = grp_to_card.get(key)
        if card and card.get("card_name"):
            return card["card_name"]
        token = tokens.get(key)
        if token and token.get("label"):
            return token["label"]
        arena = arena_only.get(key)
        if arena and arena.get("resolves_to"):
            return f"{arena['resolves_to']} (arena-only)"
        return f"grpId_{grp_id}"

    return name_of


def _multiset_diff(engine: list[int], snapshot: list[int]) -> tuple[Counter, Counter]:
    """(engine_extra, snapshot_extra) as grpId multisets."""
    e, s = Counter(engine), Counter(snapshot)
    return e - s, s - e


def _names_signature(extra: Counter, name_of: Callable[[int], str]) -> str:
    """Sorted unique display names of a multiset diff (counts are metadata,
    not key material, so identical identities with differing multiplicities
    share a cluster)."""
    return ",".join(sorted({name_of(g) for g in extra}))


# ---------------------------------------------------------------------------
# Cluster keys (total: every record maps to exactly one key)
# ---------------------------------------------------------------------------


def cluster_key(
    record: dict[str, Any], name_of: Callable[[int], str]
) -> tuple[str, ...]:
    bucket = bucket_of(record)
    desc = record["description"]

    if bucket == "zone_contents":
        parsed = parse_zone(desc)
        if parsed is None:
            return (bucket, "UNPARSED", desc[:60])
        engine_extra, snap_extra = _multiset_diff(parsed["engine"], parsed["snapshot"])
        if engine_extra and snap_extra:
            direction = "both"
            sig = (
                f"engine+{{{_names_signature(engine_extra, name_of)}}}"
                f"|snapshot+{{{_names_signature(snap_extra, name_of)}}}"
            )
        elif engine_extra:
            direction = "engine_extra"
            sig = _names_signature(engine_extra, name_of)
        elif snap_extra:
            direction = "snapshot_extra"
            sig = _names_signature(snap_extra, name_of)
        else:  # equal multisets can't mismatch, but stay total regardless
            direction, sig = "no_diff", ""
        return (bucket, parsed["zone"], direction, sig)

    if bucket == "power_toughness":
        parsed = parse_pt(desc)
        if parsed is None:
            return (bucket, "UNPARSED", desc[:60])
        return (bucket, parsed["card"])

    if bucket == "tapped_state":
        parsed = parse_tapped(desc)
        if parsed is None:
            return (bucket, "UNPARSED", desc[:60])
        return (bucket, parsed["card"])

    if bucket == "life_total":
        parsed = parse_life(desc)
        if parsed is None:
            return (bucket, "UNPARSED", desc[:60])
        delta = parsed["engine"] - parsed["snapshot"]
        sign = "engine_high" if delta > 0 else "engine_low"
        magnitude = min(abs(delta), LIFE_DELTA_CAP)
        cap = f"{magnitude}+" if abs(delta) >= LIFE_DELTA_CAP else str(magnitude)
        return (bucket, f"seat {parsed['seat']}", sign, f"delta {cap}")

    if bucket == "ILLEGAL_ACTION":
        inner = "unknown"
        if desc.startswith("[") and "]" in desc:
            inner = desc[1 : desc.index("]")]
        action_type = record.get("action_type") or "?"
        action_card = record.get("action_card") or "?"
        return (bucket, inner, action_type, action_card)

    if bucket == "ENGINE_ERROR":
        parsed = parse_engine_error(desc)
        if parsed is None:
            return (bucket, "UNPARSED", desc[:60])
        return (bucket, parsed["verb"], parsed["card"] or "-", parsed["exc"] or "-")

    if bucket == "MISSING_CARD":
        parsed = parse_missing(desc)
        if parsed is None:
            return (bucket, "UNPARSED", desc[:60])
        return (bucket, parsed["kind"], parsed["identity"])

    if bucket == "REPLAY_INFRA":
        return (bucket, re.sub(r"\d+", "N", desc))

    # Unknown bucket (future divergence types): keyed by bucket alone so the
    # partition stays total and the new type is loudly visible.
    return (bucket, "UNPARSED", desc[:60])


def is_unparsed(key: tuple[str, ...]) -> bool:
    return len(key) > 1 and key[1] == "UNPARSED"


# ---------------------------------------------------------------------------
# Cluster construction
# ---------------------------------------------------------------------------


def _cluster_metadata(
    bucket: str,
    records: list[dict[str, Any]],
    name_of: Callable[[int], str],
) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if bucket == "power_toughness":
        dims: Counter[str] = Counter()
        deltas: Counter[str] = Counter()
        for rec in records:
            parsed = parse_pt(rec["description"])
            if parsed:
                dims[parsed["dimension"]] += 1
                deltas[str(parsed["engine"] - parsed["snapshot"])] += 1
        meta["by_dimension"] = dict(sorted(dims.items()))
        meta["engine_minus_snapshot_histogram"] = dict(sorted(deltas.items()))
    elif bucket == "tapped_state":
        direction: Counter[str] = Counter()
        for rec in records:
            parsed = parse_tapped(rec["description"])
            if parsed:
                direction["engine_tapped" if parsed["engine"] else "snapshot_tapped"] += 1
        meta["direction"] = dict(sorted(direction.items()))
    elif bucket == "zone_contents":
        seats: Counter[str] = Counter()
        extra_sizes: Counter[str] = Counter()
        for rec in records:
            parsed = parse_zone(rec["description"])
            if parsed:
                seats[f"seat {parsed['seat']}"] += 1
                engine_extra, snap_extra = _multiset_diff(
                    parsed["engine"], parsed["snapshot"]
                )
                extra_sizes[str(sum(engine_extra.values()) + sum(snap_extra.values()))] += 1
        meta["seat_histogram"] = dict(sorted(seats.items()))
        meta["diff_size_histogram"] = dict(sorted(extra_sizes.items()))
    elif bucket == "life_total":
        action_types: Counter[str] = Counter()
        action_cards: Counter[str] = Counter()
        for rec in records:
            action_types[rec.get("action_type") or "?"] += 1
            if rec.get("action_card"):
                action_cards[rec["action_card"]] += 1
        meta["action_type_histogram"] = dict(sorted(action_types.items()))
        meta["action_card_top"] = dict(
            sorted(action_cards.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        )
    elif bucket == "ENGINE_ERROR":
        messages: Counter[str] = Counter()
        for rec in records:
            parsed = parse_engine_error(rec["description"])
            if parsed:
                messages[parsed["msg"][:100]] += 1
        meta["message_top"] = dict(
            sorted(messages.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        )
    elif bucket == "MISSING_CARD":
        grp_ids = sorted(
            {
                parse_missing(rec["description"])["grp_id"]
                for rec in records
                if parse_missing(rec["description"])
            }
        )
        meta["grp_ids"] = grp_ids
    return meta


def _run_length_histograms(
    records: list[dict[str, Any]], keys: list[tuple[str, ...]]
) -> dict[tuple[str, ...], Counter]:
    """Per-cluster histogram of consecutive same-cluster runs within a game.

    Long runs mean one missed event whose effect persists snapshot after
    snapshot; short runs mean many distinct events.
    """
    runs: dict[tuple[str, ...], Counter] = defaultdict(Counter)
    prev: tuple[Any, ...] | None = None
    length = 0
    for rec, key in zip(records, keys):
        marker = (rec.get("game"), key)
        if marker == prev:
            length += 1
        else:
            if prev is not None:
                runs[prev[1]][str(length)] += 1
            prev, length = marker, 1
    if prev is not None:
        runs[prev[1]][str(length)] += 1
    return runs


def _limitation_reconciliation(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconcile the machine-checked ``limitation`` tags (Phase M).

    The report serializer tags every simulate-mode divergence with exactly one
    limitation class. This block proves that partition: every record carries a
    known tag (``complete``), the per-tag counts sum to the record total, and
    no unknown tag slipped in. Reports produced before Phase M (observer mode,
    or older simulate reports) carry no tags — ``available`` is then False and
    completeness is not enforced.
    """
    tags = [rec.get("limitation") for rec in records]
    available = any(t is not None for t in tags)
    by_tag: Counter[str] = Counter(t for t in tags if t is not None)
    untagged = sum(1 for t in tags if t is None)
    # Only validate against the known set when it could be imported; otherwise
    # a standalone run cannot judge tag validity and must not false-flag.
    known = set(_KNOWN_LIMITATION_TAGS)
    unknown_tags = (
        sorted({t for t in tags if t is not None and t not in known})
        if known
        else []
    )
    floor = sorted(t for t in by_tag if t in _FLOOR_LIMITATION_TAGS)
    return {
        "available": available,
        "records": len(records),
        "tagged": len(records) - untagged,
        "untagged": untagged,
        "by_tag": dict(sorted(by_tag.items(), key=lambda kv: (-kv[1], kv[0]))),
        "floor_tags": floor,
        "floor_records": sum(by_tag[t] for t in floor),
        "unknown_tags": unknown_tags,
        "complete": available and untagged == 0 and not unknown_tags,
    }


def build_triage(
    report: dict[str, Any],
    name_of: Callable[[int], str],
    source_report: str = "",
) -> dict[str, Any]:
    """Partition every divergence record into ranked root-cause clusters."""
    records = report["divergences"]
    keys = [cluster_key(rec, name_of) for rec in records]

    by_key: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for rec, key in zip(records, keys):
        by_key[key].append(rec)

    bucket_totals: Counter[str] = Counter(bucket_of(rec) for rec in records)
    run_lengths = _run_length_histograms(records, keys)
    has_attribution = any(rec.get("game") for rec in records)

    clusters = []
    for key, recs in by_key.items():
        bucket = key[0]
        games = sorted({rec.get("game") or "unknown" for rec in recs})
        game_counts = Counter(rec.get("game") or "unknown" for rec in recs)
        # One exemplar per distinct game where possible, deterministic order.
        exemplars = []
        seen_games: set[str] = set()
        for rec in sorted(
            recs,
            key=lambda r: (r.get("game") or "", r["game_state_id"], r["description"]),
        ):
            game = rec.get("game") or "unknown"
            if game in seen_games and len(seen_games) < len(games):
                continue
            if len(exemplars) >= MAX_EXEMPLARS:
                break
            seen_games.add(game)
            exemplars.append(
                {
                    "game": rec.get("game"),
                    "game_state_id": rec["game_state_id"],
                    "turn_number": rec.get("turn_number"),
                    "action_type": rec.get("action_type"),
                    "action_card": rec.get("action_card"),
                    "description": rec["description"],
                }
            )
        metadata = _cluster_metadata(bucket, recs, name_of)
        if bucket in ("life_total", "zone_contents"):
            metadata["consecutive_run_histogram"] = dict(
                sorted(run_lengths.get(key, Counter()).items(), key=lambda kv: int(kv[0]))
            )
        clusters.append(
            {
                "key": " | ".join(key),
                "bucket": bucket,
                "count": len(recs),
                "games": len(games),
                "top_games": dict(
                    sorted(game_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
                ),
                "metadata": metadata,
                "exemplars": exemplars,
                "unparsed": is_unparsed(key),
            }
        )

    clusters.sort(key=lambda c: (-c["count"], c["key"]))
    for rank, cluster in enumerate(clusters, start=1):
        cluster["rank"] = rank

    clustered_by_bucket: Counter[str] = Counter()
    for cluster in clusters:
        clustered_by_bucket[cluster["bucket"]] += cluster["count"]
    unparsed_records = sum(c["count"] for c in clusters if c["unparsed"])

    reconciliation = {
        "records": len(records),
        "total_divergences_reported": report.get("total_divergences"),
        "clusters_sum": sum(c["count"] for c in clusters),
        "by_bucket": {
            bucket: {
                "records": bucket_totals[bucket],
                "clustered": clustered_by_bucket[bucket],
            }
            for bucket in sorted(bucket_totals)
        },
        "unparsed_records": unparsed_records,
        "exact": (
            sum(c["count"] for c in clusters) == len(records)
            and len(records) == report.get("total_divergences")
            and all(
                bucket_totals[b] == clustered_by_bucket[b] for b in bucket_totals
            )
        ),
    }

    # Zone-card involvement: which identities appear in zone diffs, across
    # clusters. Overlapping by design (a record can involve several names) —
    # NOT a partition; use it to find card-shaped causes across zone clusters.
    involvement: dict[str, dict[str, Any]] = {}
    involvement_clusters: dict[str, set[str]] = defaultdict(set)
    involvement_counts: Counter[str] = Counter()
    for rec, key in zip(records, keys):
        if key[0] not in ("zone_contents", "ILLEGAL_ACTION"):
            continue
        parsed = parse_zone(rec["description"])
        if not parsed:
            continue
        engine_extra, snap_extra = _multiset_diff(parsed["engine"], parsed["snapshot"])
        for grp in set(engine_extra) | set(snap_extra):
            name = name_of(grp)
            involvement_counts[name] += 1
            involvement_clusters[name].add(" | ".join(key))
    for name in sorted(involvement_counts):
        involvement[name] = {
            "records": involvement_counts[name],
            "clusters": len(involvement_clusters[name]),
        }

    return {
        "source_report": source_report,
        "convention": CONVENTION,
        "attribution_available": has_attribution,
        "totals": {
            "records": len(records),
            "by_bucket": dict(sorted(bucket_totals.items(), key=lambda kv: (-kv[1], kv[0]))),
        },
        "reconciliation": reconciliation,
        "limitation_reconciliation": _limitation_reconciliation(records),
        "clusters": clusters,
        "zone_card_involvement": involvement,
    }


# ---------------------------------------------------------------------------
# Transcript slices
# ---------------------------------------------------------------------------


def attach_slices(
    triage: dict[str, Any],
    corpus_root: Path,
    card_id_map_flat: dict[int, str],
    top_n: int,
) -> None:
    """Attach ±SLICE_RADIUS transcript slices to top-N clusters' exemplars.

    Groups requests per game so each replay is parsed exactly once.
    Requires the report to carry ``game`` attribution; otherwise a note is
    recorded and nothing is attached.
    """
    if not triage["attribution_available"]:
        triage["slices"] = "unavailable: report lacks game attribution fields"
        return
    from silverquillm.replay.parser import parse_replay

    wanted: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cluster in triage["clusters"][:top_n]:
        for exemplar in cluster["exemplars"]:
            if exemplar.get("game"):
                wanted[exemplar["game"]].append(exemplar)

    for game in sorted(wanted):
        game_path = corpus_root / game
        try:
            replay = parse_replay(game_path, card_id_map=card_id_map_flat)
        except Exception as exc:  # noqa: BLE001 — slice failure must not kill triage
            for exemplar in wanted[game]:
                exemplar["slice"] = f"unavailable: parse failed ({type(exc).__name__})"
            continue
        snapshots = replay.snapshots
        index_of = {snap.game_state_id: i for i, snap in enumerate(snapshots)}
        for exemplar in wanted[game]:
            idx = index_of.get(exemplar["game_state_id"])
            if idx is None:
                exemplar["slice"] = "unavailable: gameStateId not in transcript"
                continue
            window = snapshots[max(0, idx - SLICE_RADIUS) : idx + SLICE_RADIUS + 1]
            exemplar["slice"] = [
                {
                    "gsid": snap.game_state_id,
                    "turn": snap.turn_info.turn_number,
                    "phase": snap.turn_info.phase,
                    "step": snap.turn_info.step,
                    "actions": [
                        " ".join(
                            part
                            for part in (
                                action.action_type,
                                action.card_name or (f"grpId_{action.grp_id}" if action.grp_id else ""),
                                f"seat={action.player_seat_id}",
                            )
                            if part
                        )
                        for action in snap.actions
                    ],
                    "annotation_types": dict(
                        sorted(
                            Counter(
                                ann_type
                                for ann in snap.annotations
                                for ann_type in ann.type
                            ).items()
                        )
                    ),
                }
                for snap in window
            ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_markdown(triage: dict[str, Any], md_rows: int) -> str:
    lines = [
        "# Divergence triage — ranked root-cause clusters",
        "",
        f"Source report: `{triage['source_report']}`  ",
        (
            f"Convention: `{triage['convention']}` (STATE_MISMATCH by `[category]`, "
            "operational types by type; every record in exactly one cluster)"
        ),
        "",
        "## Bucket totals",
        "",
        "| Bucket | Records |",
        "|---|---:|",
    ]
    for bucket, count in triage["totals"]["by_bucket"].items():
        lines.append(f"| {bucket} | {count} |")
    lines.append(f"| **Total** | **{triage['totals']['records']}** |")

    recon = triage["reconciliation"]
    lines += [
        "",
        (
            f"Reconciliation: clusters sum to {recon['clusters_sum']} of "
            f"{recon['records']} records "
            f"(report total {recon['total_divergences_reported']}); "
            f"exact partition: **{recon['exact']}**; "
            f"unparsed records: **{recon['unparsed_records']}**."
        ),
    ]

    lim = triage.get("limitation_reconciliation", {})
    if lim.get("available"):
        lines += [
            "",
            "## Limitation attribution (Phase M)",
            "",
            (
                f"Every record tagged: **{lim['complete']}** "
                f"({lim['tagged']}/{lim['records']}); "
                f"untagged: **{lim['untagged']}**; "
                f"floor (stream-limited): **{lim['floor_records']}** "
                f"across {lim['floor_tags']}."
            ),
            "",
            "| Limitation | Records | Kind |",
            "|---|---:|---|",
        ]
        for tag, count in lim["by_tag"].items():
            kind = "floor" if tag in _FLOOR_LIMITATION_TAGS else "family"
            lines.append(f"| {tag} | {count} | {kind} |")
        if lim["unknown_tags"]:
            lines.append(
                f"| **UNKNOWN** | — | {', '.join(lim['unknown_tags'])} |"
            )

    lines += [
        "",
        "## Clusters",
        "",
        "| # | Bucket | Cluster | Count | Games | Signal |",
        "|---:|---|---|---:|---:|---|",
    ]
    for cluster in triage["clusters"][:md_rows]:
        key_display = cluster["key"]
        if len(key_display) > 90:
            key_display = key_display[:87] + "..."
        meta = cluster["metadata"]
        signal = ""
        if "by_dimension" in meta:
            signal = "dims " + "/".join(f"{k}:{v}" for k, v in meta["by_dimension"].items())
        elif "direction" in meta:
            signal = "/".join(f"{k}:{v}" for k, v in meta["direction"].items())
        elif meta.get("consecutive_run_histogram"):
            longest = max(int(k) for k in meta["consecutive_run_histogram"])
            signal = f"longest run {longest}"
        elif meta.get("message_top"):
            signal = next(iter(meta["message_top"]))[:60]
        elif "grp_ids" in meta:
            signal = "grpIds " + ",".join(str(g) for g in meta["grp_ids"][:4])
        lines.append(
            f"| {cluster['rank']} | {cluster['bucket']} | `{key_display}` "
            f"| {cluster['count']} | {cluster['games']} | {signal} |"
        )
    if len(triage["clusters"]) > md_rows:
        remaining = triage["clusters"][md_rows:]
        lines.append(
            f"| — | — | *…{len(remaining)} more clusters "
            f"({sum(c['count'] for c in remaining)} records) — see JSON* | | | |"
        )

    involvement = triage["zone_card_involvement"]
    if involvement:
        lines += [
            "",
            "## Zone-diff card involvement (overlapping index, not a partition)",
            "",
            "| Identity | Records | Clusters |",
            "|---|---:|---:|",
        ]
        ranked = sorted(
            involvement.items(), key=lambda kv: (-kv[1]["records"], kv[0])
        )[:40]
        for name, info in ranked:
            lines.append(f"| {name} | {info['records']} | {info['clusters']} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        with open(path) as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report", type=Path, help="validation report JSON")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top", type=int, default=40, help="clusters that get transcript slices")
    parser.add_argument("--md-rows", type=int, default=200, help="clusters shown in the markdown table")
    parser.add_argument("--no-slices", action="store_true", help="skip transcript slice extraction")
    args = parser.parse_args(argv)

    report = _load_json(args.report)
    if report is None or "divergences" not in report:
        print(f"error: not a validation report: {args.report}", file=sys.stderr)
        return 2

    name_of = build_name_resolver(
        _load_json(CARD_ID_MAP_PATH), _load_json(TOKEN_ID_MAP_PATH)
    )
    triage = build_triage(report, name_of, source_report=str(args.report))

    if not args.no_slices:
        card_map = _load_json(CARD_ID_MAP_PATH) or {}
        flat = {
            int(grp): info.get("card_name", "")
            for grp, info in card_map.get("grpId_to_card", {}).items()
        }
        attach_slices(triage, args.corpus, flat, args.top)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.report.stem
    json_path = args.out_dir / f"triage_{stem}.json"
    md_path = args.out_dir / f"triage_{stem}.md"
    with open(json_path, "w") as handle:
        json.dump(triage, handle, indent=2, sort_keys=True)
        handle.write("\n")
    md_path.write_text(render_markdown(triage, args.md_rows))

    recon = triage["reconciliation"]
    lim = triage["limitation_reconciliation"]
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        f"records={recon['records']} clusters={len(triage['clusters'])} "
        f"clustered={recon['clusters_sum']} unparsed={recon['unparsed_records']} "
        f"exact={recon['exact']}"
    )
    if lim["available"]:
        print(
            f"limitation: tagged={lim['tagged']}/{lim['records']} "
            f"floor={lim['floor_records']} complete={lim['complete']} "
            f"untagged={lim['untagged']} unknown={lim['unknown_tags']}"
        )
    if not recon["exact"]:
        print("error: cluster partition does not reconcile", file=sys.stderr)
        return 1
    # A tagged report that leaves any divergence untagged (or carries an
    # unknown tag) fails the Phase M acceptance gate: zero untagged survivors.
    if lim["available"] and not lim["complete"]:
        print(
            "error: limitation attribution incomplete "
            f"(untagged={lim['untagged']} unknown={lim['unknown_tags']})",
            file=sys.stderr,
        )
        return 4
    if recon["unparsed_records"]:
        print("warning: UNPARSED records present (see clusters)", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
