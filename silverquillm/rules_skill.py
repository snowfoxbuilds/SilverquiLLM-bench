"""MTG comprehensive rules grep-based lookup.

Thin wrapper around the cached comprehensive-rules text file.  The rules file
is a plain-text, greppable document — this module provides three helpers:

* ``download_comprehensive_rules`` — fetch/cache the rules text.
* ``build_rules_index`` — parse numbered rules into a ``dict[str, list[str]]``.
* ``lookup_rule`` — grep the index by rule number or keyword.
"""

from __future__ import annotations

import logging
import re
import urllib.request
from pathlib import Path

__all__ = [
    "download_comprehensive_rules",
    "build_rules_index",
    "lookup_rule",
]

logger = logging.getLogger(__name__)

_RULES_URL = (
    "https://media.wizards.com/images/magic/comprules/MagicCompRules.txt"
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "sos" / "data"
_CACHE_PATH = _DATA_DIR / "comprehensive_rules.txt"

# Rule-number pattern: e.g. "100.", "100.1", "100.1a", "702.9b"
_RULE_RE = re.compile(r"^(\d{3}(?:\.\d+[a-z]?)?)\.?\s+(.+)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def download_comprehensive_rules(*, force: bool = False) -> str:
    """Return the comprehensive rules text, downloading and caching if needed."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not force and _CACHE_PATH.exists():
        return _CACHE_PATH.read_text(encoding="utf-8")

    try:
        req = urllib.request.Request(
            _RULES_URL, headers={"User-Agent": "SilverquiLLM-bench/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
    except Exception:
        logger.warning("Failed to download rules; using cached stub.", exc_info=True)
        # Stub is already on disk from initial repo setup; return it.
        if _CACHE_PATH.exists():
            return _CACHE_PATH.read_text(encoding="utf-8")
        # Minimal embedded fallback so build_rules_index/lookup_rule stay functional.
        text = (
            "1. Game Concepts\n"
            "100.1 These Magic rules apply to any Magic game with two or more players.\n"
            "100.2 To play, each player needs their own deck.\n"
            "2. Parts of a Card\n"
            "200.1 The parts of a card are name, mana cost, illustration, color indicator, "
            "type line, expansion symbol, text box, power and toughness, loyalty, hand "
            "modifier, life modifier, illustration credit, legal text, and collector number.\n"
            "3. Card Types\n"
            "300.1 The card types are artifact, battle, conspiracy, creature, dungeon, "
            "enchantment, instant, land, phenomenon, plane, planeswalker, scheme, sorcery, "
            "tribal, and vanguard.\n"
            "4. Zones\n"
            "400.1 A zone is a place where objects can be during a game. There are normally "
            "seven zones: library, hand, battlefield, graveyard, stack, exile, and command.\n"
            "5. Turn Structure\n"
            "500.1 A turn consists of five phases, in this order: beginning, precombat main, "
            "combat, postcombat main, and ending.\n"
            "6. Spells, Abilities, and Effects\n"
            "601.1 Previously, a player could cast a spell only during the main phase of their "
            "turn. This rule has been updated.\n"
            "7. Additional Rules\n"
            "700.1 Anything that happens in a game is an event.\n"
            "702.1 Keyword abilities are abilities that are so common they have been given "
            "their own keyword. Flying, trample, haste, and vigilance are keyword abilities.\n"
            "702.9 Flying is an evasion ability.\n"
            "702.9a A creature with flying can't be blocked except by creatures with flying "
            "and/or reach.\n"
        )
        logger.warning("Using minimal embedded rules fallback.")

    if text:
        _CACHE_PATH.write_text(text, encoding="utf-8")
    return text


def build_rules_index(rules_text: str) -> dict[str, list[str]]:
    """Parse *rules_text* into ``{rule_number: [lines…]}`` plus keyword entries.

    Two kinds of keys are produced:

    * **Rule numbers** (``"702.9"``) → list of rule-text lines.
    * **``kw:<word>``** → list of rule numbers whose text contains *word*.
    """
    index: dict[str, list[str]] = {}

    for match in _RULE_RE.finditer(rules_text):
        num, text = match.group(1), match.group(2).strip()
        index.setdefault(num, []).append(text)
        parent = _parent_rule(num)
        if parent and parent != num:
            index.setdefault(parent, []).append(f"{num} {text}")

    # Keyword map: word → set of rule numbers
    kw_map: dict[str, set[str]] = {}
    for num, texts in index.items():
        if num.startswith("kw:"):
            continue
        for word in set(re.findall(r"[a-z]+", " ".join(texts).lower())):
            if len(word) >= 3:
                kw_map.setdefault(word, set()).add(num)

    # Glossary entries (if present)
    in_glossary = False
    for line in rules_text.split("\n"):
        if line.strip().lower() == "glossary:":
            in_glossary = True
            continue
        if in_glossary:
            gm = re.match(r"^([A-Z][A-Za-z ]+?):\s+(.+)", line)
            if gm:
                term = gm.group(1).strip().lower()
                refs = re.findall(r"\d{3}(?:\.\d+[a-z]?)?", gm.group(2))
                for w in term.split():
                    if len(w) >= 3:
                        for ref in refs:
                            kw_map.setdefault(w, set()).add(ref)

    for kw, nums in kw_map.items():
        index[f"kw:{kw}"] = sorted(nums)

    return index


def lookup_rule(index: dict[str, list[str]], query: str) -> str:
    """Grep *index* for *query* (rule number or keyword). Returns matched text."""
    query = query.strip()

    # Exact rule-number hit
    if query in index:
        return _fmt(query, index[query])

    # Keyword hit
    kw_key = f"kw:{query.lower()}"
    if kw_key in index:
        parts = [
            _fmt(n, index[n]) for n in dict.fromkeys(index[kw_key]) if n in index
        ]
        if parts:
            return "\n\n".join(parts)

    # Prefix match on rule numbers
    if re.match(r"^\d+", query):
        parts = [
            _fmt(k, index[k])
            for k in sorted(index) if k.startswith(query) and not k.startswith("kw:")
        ]
        if parts:
            return "\n\n".join(parts[:10])

    # Full-text grep fallback
    q = query.lower()
    hits = [
        f"[{k}] {t}"
        for k, texts in sorted(index.items()) if not k.startswith("kw:")
        for t in texts if q in t.lower()
    ]
    if hits:
        return "\n".join(hits[:10])

    return f"No rules found for query: {query!r}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parent_rule(num: str) -> str | None:
    """``'702.9a'`` → ``'702.9'``, ``'702.9'`` → ``'702'``, ``'702'`` → None."""
    if re.match(r"^\d+\.\d+[a-z]$", num):
        return num[:-1]
    if re.match(r"^\d+\.\d+$", num):
        return num.split(".")[0]
    return None


def _fmt(num: str, texts: list[str]) -> str:
    return f"Rule {num}:\n  " + "\n  ".join(texts)
