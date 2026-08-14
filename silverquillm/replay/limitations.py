"""Machine-checked limitation attribution for surviving replay divergences.

Phase M (issue #40 capstone). Every divergence the simulate-mode validator
records is mapped to exactly one named *limitation class* by
:func:`classify_limitation` — a **total** function (no divergence is left
untagged). The taxonomy has two kinds of tag:

* **floor** — a genuine stream limitation: the corpus cannot carry the
  distinguishing evidence, so no faithful engine could reproduce GRE. These
  form the "attributed floor". Each is proven on a fixture by a mechanism test
  (``tests/test_replay_limitations.py`` / workspace
  ``engine_tests/test_replay_limitations.py``) that shows the stream lacks the
  distinguishing evidence.
* **family** — an attributed engine/card-gap family that is fixable in
  principle (future card/engine work), not a hard floor. Also mechanism-tested
  for its defining property.

The classifier is invoked simulate-gated at the report serializer
(:func:`silverquillm.replay.cli._divergence_record`), so observer-mode reports
stay byte-identical — a divergence's ``limitation`` field is only written when
``simulate`` is set.

The tag is derived from the record's own fields (type, description, action
attribution) plus two evidence inputs the executor/maps supply on a
:class:`LimitationContext`:

* ``ambiguous_sources`` — names of multi-ability sources whose exact ability
  the executor could not disambiguate from the observed GRE delta (recorded at
  the refusal site in ``executor._try_activate_ability``); their surviving
  state mismatches are the ``ambiguous-ability`` floor.
* ``token_grp_ids`` — grpIds the token map knows as minted tokens, used to tell
  an unminted GRE token (``unimplemented-effect``) from a real card whose zone
  timing merely lags (``resolution-cadence``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

FLOOR = "floor"
FAMILY = "family"

# tag -> (kind, one-line summary for the report's floor table).
LIMITATION_TAGS: dict[str, tuple[str, str]] = {
    # --- the attributed floor: genuine stream limitations ---
    "unfunded-activation": (
        FLOOR,
        (
            "the activation/cast cost is not covered by any stream-attested "
            "resource (no ManaPaid within look-ahead, no attested manaPool, or "
            "a card-private counter cost the stream never carries)"
        ),
    ),
    "ambiguous-ability": (
        FLOOR,
        (
            "a multi-ability source whose exact ability the stream "
            "under-determines — GRE carries no per-card ability-grpId map, so "
            ">=2 candidate predictions match the observed delta and the "
            "executor refuses to guess"
        ),
    ),
    "hidden-information": (
        FLOOR,
        (
            "the compared value depends on zone content GRE does not attest to "
            "the observing seat (grpId 0 hidden hand/library shells, a "
            "library-driven power/toughness, or an out-of-set/unmappable token "
            "identity)"
        ),
    ),
    # --- attributed engine/card-gap families (fixable, future work) ---
    "driving-context": (
        FAMILY,
        (
            "the executor could not reconstruct the exact driven cast/activation "
            "from the stream (no legal target, sorcery-speed or timing/zone "
            "context the drive-time engine state does not match)"
        ),
    ),
    "unimplemented-effect": (
        FAMILY,
        (
            "GRE attests a token/effect the engine's card implementation does "
            "not yet produce (a dormant upkeep/end-step minter or an "
            "unimplemented token identity)"
        ),
    ),
    "resolution-cadence": (
        FAMILY,
        (
            "the engine produces the effect but applies it at a different "
            "snapshot boundary than GRE (a bounded, resync-corrected timing "
            "offset in zone/life/tapped/power-toughness or a creature-death race)"
        ),
    ),
    "replay-infra": (
        FAMILY,
        (
            "an executor-side harness impossibility (engine library empty on a "
            "GRE-observed draw, step-event plumbing) — kept distinct from "
            "engine/card bugs"
        ),
    ),
}

FLOOR_TAGS = frozenset(t for t, (kind, _) in LIMITATION_TAGS.items() if kind == FLOOR)

# Cards whose power/toughness is a function of a hidden zone (the library, via
# self-mill feeding the graveyard count). The engine's hidden library differs
# from GRE's, so the derived P/T is unrecoverable from the stream — a genuine
# floor. Verified the single such card in the FDN corpus; any other dynamic P/T
# is a resolution-cadence family member, not a claimed floor (under-claiming the
# floor is the conservative, honest direction). See the mechanism test.
HIDDEN_PT_CARDS = frozenset({"Consuming Aberration"})

# Token grpIds whose identity the stream cannot recover because a same-colour,
# same-signature copy token collides with them map-wide, so the token correlator
# REFUSES to guess which one a battlefield object is (the locked identity rule).
# A genuine hidden-information floor, proven by the co-presence mechanism test:
# these are the only tokens that appear id-less on the engine battlefield at the
# same snapshot GRE attests them yet are never stamped. The single such identity
# in the FDN corpus is the 1/1 black Rat 94169, indistinguishable from the 1/1
# black Burglar Rat copy 93883 (same colour, no copy name on the generic token).
CORRELATION_REFUSED_TOKENS = frozenset({94169})

# Parses ``grpId=<n>`` out of a token MISSING_CARD description.
_RE_MISSING_TOKEN_GRP = re.compile(r"grpId=(?P<grp>\d+)")


@dataclass
class LimitationContext:
    """Evidence the classifier consults beyond the record's own fields."""

    ambiguous_sources: frozenset[str] = field(default_factory=frozenset)
    token_grp_ids: frozenset[int] = field(default_factory=frozenset)
    # Phase O (issue #57): token grpIds a real engine impl minted in THIS game,
    # whether or not the mint ever correlated. A snapshot-extra token here is a
    # mint-cadence offset (the impl produces it; the engine merely applied it at
    # a different snapshot boundary than GRE), so it is a resolution-cadence
    # divergence rather than an unimplemented-effect one.
    impl_minted_token_grpids: frozenset[int] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Minimal parsers (independent of scripts/triage_divergences.py so the report
# serializer carries no script dependency; kept deliberately small).
# ---------------------------------------------------------------------------

_RE_CATEGORY = re.compile(r"^\[(?P<cat>[a-z_]+)\]")
_RE_PT_TAPPED_CARD = re.compile(
    r"^\[(?:power_toughness|tapped_state)\] (?P<card>.+?) "
    r"(?:power|toughness|tapped state) mismatch:"
)
_RE_ZONE_LISTS = re.compile(
    r"engine=\[(?P<engine>[^\]]*)\], snapshot=\[(?P<snap>[^\]]*)\]"
)
_RE_MISSING_GRP = re.compile(r"\(grpId=(?P<grp>\d+)\)")


def _category(desc: str) -> str | None:
    m = _RE_CATEGORY.match(desc)
    return m["cat"] if m else None


def _pt_or_tapped_card(desc: str) -> str | None:
    m = _RE_PT_TAPPED_CARD.match(desc)
    return m["card"] if m else None


def _int_list(text: str) -> list[int]:
    return [int(tok) for tok in text.split(",") if tok.strip()]


def _zone_multiset_diff(desc: str) -> tuple[list[int], list[int]] | None:
    """Return (engine_extra, snapshot_extra) grpId lists for a zone mismatch."""
    m = _RE_ZONE_LISTS.search(desc)
    if not m:
        return None
    from collections import Counter

    engine = Counter(_int_list(m["engine"]))
    snap = Counter(_int_list(m["snap"]))
    engine_extra = list((engine - snap).elements())
    snap_extra = list((snap - engine).elements())
    return engine_extra, snap_extra


# ---------------------------------------------------------------------------
# The total classifier
# ---------------------------------------------------------------------------


def classify_limitation(record: dict, context: LimitationContext) -> str:
    """Return the single limitation tag for one serialized divergence record.

    Total: every record maps to exactly one tag in :data:`LIMITATION_TAGS`.
    """
    dtype = record.get("type", "")
    desc = record.get("description", "") or ""

    if dtype == "ENGINE_ERROR":
        low = desc.lower()
        if "cost could not be paid" in low or "insufficient mana" in low:
            return "unfunded-activation"
        # no legal target / sorcery-speed timing / illegal (timing or zone) /
        # other casting errors: the driven action's exact parameters are not
        # reconstructable from the stream.
        return "driving-context"

    if dtype == "REPLAY_INFRA":
        return "replay-infra"

    if dtype in ("QUERY_UNANSWERED", "PROTOCOL_ERROR"):
        # intent/boundary reconstruction failures (0 in the FDN corpus).
        return "driving-context"

    if dtype == "MISSING_CARD":
        if "out-of-set" in desc or "out-of-registry" in desc:
            return "hidden-information"
        m = _RE_MISSING_TOKEN_GRP.search(desc)
        if m and int(m["grp"]) in CORRELATION_REFUSED_TOKENS:
            # A same-colour copy collision the correlator refuses to guess —
            # its identity is unrecoverable from the stream (floor), not a
            # missing minter.
            return "hidden-information"
        return "unimplemented-effect"

    # STATE_MISMATCH and ILLEGAL_ACTION both carry a leading [category].
    category = _category(desc)

    if category in ("power_toughness", "tapped_state"):
        card = _pt_or_tapped_card(desc) or record.get("action_card")
        if card and card in context.ambiguous_sources:
            return "ambiguous-ability"
        if category == "power_toughness" and card in HIDDEN_PT_CARDS:
            return "hidden-information"
        return "resolution-cadence"

    if category == "life_total":
        return "resolution-cadence"

    if category == "zone_contents":
        diff = _zone_multiset_diff(desc)
        if diff is None:
            return "resolution-cadence"
        engine_extra, snap_extra = diff
        # A same-colour copy collision the correlator refuses to guess -> the
        # identity is unrecoverable from the stream (floor), not a missing minter.
        if any(g in CORRELATION_REFUSED_TOKENS for g in snap_extra):
            return "hidden-information"
        # A token a real engine impl MINTED this game (Phase O) is produced -
        # the surviving snapshot-extra is a mint-cadence offset, not a missing
        # minter. Checked before the unimplemented rule so a producible token
        # that merely lands a snapshot off is attributed to the cadence family.
        if any(g in context.impl_minted_token_grpids for g in snap_extra):
            return "resolution-cadence"
        # GRE holds a minted token the engine never produced -> unimplemented.
        if any(g in context.token_grp_ids for g in snap_extra):
            return "unimplemented-effect"
        differing = set(engine_extra) | set(snap_extra)
        # Only identity-less shells differ -> the stream never attested identity.
        if differing and all(g == 0 for g in differing):
            return "hidden-information"
        # Real card (or an engine-extra token minted a snapshot early/late):
        # a zone-timing offset.
        return "resolution-cadence"

    # Unknown / future state category: attribute to the cadence family so the
    # partition stays total and the new shape is visible in the report.
    return "resolution-cadence"
