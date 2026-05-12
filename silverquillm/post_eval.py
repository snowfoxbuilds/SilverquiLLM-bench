"""Post-run evaluation phase.

After the card loop completes (workspace setup → strategy.run_card() →
harvest → postmortem → next card), this module runs all evaluation tests
against the **final** engine state.

Public API:
- ``CardEvalResult`` — per-card evaluation outcome dataclass.
- ``run_post_eval`` — evaluate all cards in a completed run directory.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from silverquillm.evaluator import run_tests

logger = logging.getLogger(__name__)

__all__ = [
    "CardEvalResult",
    "run_post_eval",
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CardEvalResult:
    """Outcome of post-run evaluation for a single card."""

    card_id: str
    self_eval_passed: int = 0
    self_eval_failed: int = 0
    self_eval_total: int = 0
    audited_passed: int = 0
    audited_failed: int = 0
    audited_total: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Post-run evaluation
# ---------------------------------------------------------------------------


def run_post_eval(
    run_dir: Path,
    mode: str,
    audited_dir: Path | None = None,
) -> list[CardEvalResult]:
    """Run evaluation for all cards after the run loop completes.

    For each card directory under ``run_dir/cards/``:

    1. **Self-eval** (``impl_test`` mode only): runs the card's own
       ``tests.py`` against ``card_impl.py``.
    2. **Audited eval** (when *audited_dir* is provided): runs the
       audited test file at
       ``audited_dir/{set_code}/{collector_number}/tests.py``
       against ``card_impl.py``.

    All tests execute against the final engine state—i.e. the
    ``run_dir/engine/`` directory as it exists after the last card
    was processed.

    Results are written back to each card's ``result.json``.

    Parameters
    ----------
    run_dir:
        Root of the completed run (contains ``cards/`` and ``engine/``).
    mode:
        Benchmark mode (``"blind"`` or ``"impl_test"``).
    audited_dir:
        Optional root directory for audited tests.  Expected layout::

            audited_dir/{set_code}/{collector_number}/tests.py

    Returns
    -------
    list[CardEvalResult]
        One result per card directory found under ``run_dir/cards/``.
    """
    cards_dir = run_dir / "cards"
    if not cards_dir.exists():
        return []

    # Resolve the run-level engine directory (final state after all cards)
    engine_dir = run_dir / "engine"
    effective_engine: Path | None = engine_dir if engine_dir.is_dir() else None

    results: list[CardEvalResult] = []

    for card_path in sorted(cards_dir.iterdir()):
        if not card_path.is_dir():
            continue

        card_id = card_path.name
        impl_path = card_path / "card_impl.py"
        tests_path = card_path / "tests.py"

        card_result = CardEvalResult(card_id=card_id)

        # ----- Self-eval (impl_test mode only) -----
        if mode == "impl_test" and impl_path.exists() and tests_path.exists():
            passed, failed, total, errors = run_tests(
                impl_path, tests_path, engine_dir=effective_engine,
            )
            card_result.self_eval_passed = passed
            card_result.self_eval_failed = failed
            card_result.self_eval_total = total
            card_result.errors.extend(errors)
        elif mode == "impl_test":
            if not impl_path.exists():
                card_result.errors.append(f"Missing {impl_path}")
            if not tests_path.exists():
                card_result.errors.append(f"Missing {tests_path}")

        # ----- Audited eval -----
        if audited_dir is not None:
            _run_audited_for_card(
                card_result, impl_path, card_id, card_path, audited_dir, effective_engine,
            )

        # ----- Persist to result.json -----
        _merge_result_json(card_path, card_result, mode=mode)

        results.append(card_result)

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_audited_tests(
    card_id: str,
    card_path: Path,
    audited_dir: Path,
) -> Path | None:
    """Deterministically locate the audited test file for a card.

    Resolution order:

    1. If the card's ``result.json`` contains a ``set_code`` field, look at
       ``audited_dir/{set_code}/{card_id}/tests.py``.
    2. Fall back to the flat layout ``audited_dir/{card_id}/tests.py``.

    Returns the path to ``tests.py`` if found, otherwise ``None``.
    """
    # Try set_code from card metadata first (deterministic)
    result_json = card_path / "result.json"
    if result_json.exists():
        try:
            meta = json.loads(result_json.read_text())
            set_code = meta.get("set_code")
            if set_code:
                candidate = audited_dir / set_code / card_id / "tests.py"
                if candidate.exists():
                    return candidate
        except (json.JSONDecodeError, KeyError):
            pass

    # Fall back to flat layout: audited_dir/{card_id}/tests.py
    direct = audited_dir / card_id / "tests.py"
    if direct.exists():
        return direct

    return None


def _run_audited_for_card(
    card_result: CardEvalResult,
    impl_path: Path,
    card_id: str,
    card_path: Path,
    audited_dir: Path,
    engine_dir: Path | None,
) -> None:
    """Discover and run audited tests for a single card.

    Uses :func:`_resolve_audited_tests` for deterministic test lookup,
    then runs the tests while preserving the audited conftest.py layout.
    """
    if not impl_path.exists():
        card_result.errors.append(f"Missing impl for audited eval: {impl_path}")
        return

    audited_tests = _resolve_audited_tests(card_id, card_path, audited_dir)
    if audited_tests is None:
        # No audited tests for this card — not an error, just skip
        return

    passed, failed, total, errors = run_tests(
        impl_path, audited_tests, engine_dir=engine_dir,
    )
    card_result.audited_passed = passed
    card_result.audited_failed = failed
    card_result.audited_total = total
    card_result.errors.extend(errors)


def _merge_result_json(card_path: Path, card_result: CardEvalResult, mode: str = "impl_test") -> None:
    """Merge *card_result* into the card's ``result.json`` using v2 schema."""
    result_json = card_path / "result.json"
    if result_json.exists():
        record = json.loads(result_json.read_text())
    else:
        record = {"card_id": card_result.card_id}

    # Ensure v2 schema markers
    record.setdefault("schema_version", 2)
    record.setdefault("mode", mode)

    # Self-eval: only present in impl_test mode
    if mode == "impl_test" and card_result.self_eval_total > 0:
        record["self_eval"] = {
            "passed": card_result.self_eval_passed,
            "failed": card_result.self_eval_failed,
            "total": card_result.self_eval_total,
        }
    elif "self_eval" not in record:
        record["self_eval"] = None

    # Audited eval
    if card_result.audited_total > 0:
        record["audited_eval"] = {
            "passed": card_result.audited_passed,
            "failed": card_result.audited_failed,
            "total": card_result.audited_total,
        }
    elif "audited_eval" not in record:
        record["audited_eval"] = None

    if card_result.errors:
        record["eval_errors"] = record.get("eval_errors", []) + card_result.errors
        # Also store under v2 key for forward compat
        record["errors"] = record.get("errors", []) + card_result.errors

    result_json.write_text(json.dumps(record, indent=2, default=str))
