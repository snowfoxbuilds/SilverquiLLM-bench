"""Run summary generation for Docker-based benchmark runs.

Pure, idempotent function that reads per-card ``result.json`` files and
produces ``run_summary.json``.

Public API:
- ``generate_run_summary(run_dir, image_name)`` — aggregate results into summary dict.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["generate_run_summary"]


def _get_harness_version() -> str:
    """Return current git SHA or 'unknown' on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return "unknown"


def _count_engine_churn_lines(run_dir: Path) -> int:
    """Count lines in engine_diff.patch if present."""
    patch_path = run_dir / "engine_diff.patch"
    if not patch_path.exists():
        return 0
    try:
        text = patch_path.read_text(encoding="utf-8", errors="replace")
        return sum(
            1
            for line in text.splitlines()
            if line.startswith("+") or line.startswith("-")
            if not line.startswith("+++") and not line.startswith("---")
        )
    except OSError:
        return 0


def _load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _load_status_map(run_dir: Path) -> dict[str, str]:
    """Load status.json mapping collector_number → status string.

    Handles both the new dict format ``{"status": str, "card_name": str}``
    and legacy bare string format for backward compatibility.
    """
    data = _load_json(run_dir / "status.json")
    if not isinstance(data, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = value.get("status", "unknown")
        else:
            result[key] = value  # legacy bare string format
    return result


def _load_eval_result(run_dir: Path) -> dict | None:
    """Load eval_result.json if present."""
    return _load_json(run_dir / "eval_result.json")


def _parse_timestamp_from_dirname(run_dir: Path) -> str:
    """Extract ISO timestamp from run directory name.

    Expected format: ``{image}_{ISO-timestamp}`` where the timestamp
    portion uses hyphens instead of colons, e.g.
    ``opencode-tested_2026-05-14T10-30-00Z``.

    Falls back to existing ``run_summary.json`` timestamp, then directory
    mtime, and finally ``datetime.now(UTC)``.
    """
    name = run_dir.name
    # Find timestamp after the last underscore that looks like a date
    parts = name.split("_")
    for i in range(len(parts) - 1, 0, -1):
        candidate = "_".join(parts[i:])
        # Check if it starts with a date-like pattern (YYYY-MM-DD)
        if len(candidate) >= 10 and candidate[4] == "-" and candidate[7] == "-":
            # Convert hyphens in time portion back to colons
            # e.g. 2026-05-14T10-30-00Z → 2026-05-14T10:30:00Z
            # Only replace hyphens after the 'T' separator
            t_pos = candidate.find("T")
            if t_pos >= 0:
                date_part = candidate[:t_pos]
                time_part = candidate[t_pos + 1:].replace("-", ":")
                return f"{date_part}T{time_part}"
            return candidate

    # Fallback: check existing run_summary.json
    existing = _load_json(run_dir / "run_summary.json")
    if existing and isinstance(existing, dict):
        meta = existing.get("run_metadata", {})
        if isinstance(meta, dict) and "timestamp" in meta:
            return meta["timestamp"]

    # Fallback: directory mtime
    try:
        mtime = run_dir.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except OSError:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_run_summary(
    run_dir: Path,
    image_name: str,
    cards_dir: Path | None = None,
    *,
    resumed_from: str | None = None,
    resumed_image_changed: bool | None = None,
    run_status: str | None = None,
    wall_clock_seconds: float | None = None,
) -> dict:
    """Generate a run summary from per-card results under *run_dir*.

    Reads:
    - ``status.json`` — card status map (source of truth for all cards)
    - ``cards/{num}/result.json`` — per-card test results
    - ``cards_dir/{sos}/{num}/card_spec.json`` — card metadata (if *cards_dir* given)
    - ``cards/{num}/card_spec.json`` — fallback card metadata
    - ``engine_diff.patch`` — engine changes
    - ``eval_result.json`` — full evaluation result (optional)

    Writes the summary to ``run_dir/run_summary.json`` and returns it.

    Parameters
    ----------
    run_dir:
        Path to the run directory containing card results.
    image_name:
        Docker image name used for the run.
    cards_dir:
        Optional path to the original cards directory (e.g. ``cards/``).
        Used to look up ``card_spec.json`` when the harvested run directory
        does not contain it.

    Returns
    -------
    dict
        The summary structure (also written to ``run_summary.json``).
    """
    run_dir = Path(run_dir)
    status_map = _load_status_map(run_dir)
    eval_result = _load_eval_result(run_dir)

    # ---- Build per-card entries from benchmarks/sos/workspace/cards/ directory ----
    per_card: list[dict] = []
    cards_dir = run_dir / "cards"

    # Track SOS aggregation
    sos_total_passed = 0
    sos_total_tests = 0
    sos_cards_all_pass = 0
    sos_cards_completed = 0

    # Track FDN aggregation
    fdn_total_passed = 0
    fdn_total_tests = 0
    fdn_cards_all_pass = 0
    fdn_cards_total = 0

    cards_completed = 0
    cards_no_output = 0
    cards_timed_out = 0

    card_dirs: list[Path] = []
    if cards_dir.is_dir():
        card_dirs = sorted(
            [d for d in cards_dir.iterdir() if d.is_dir()],
            key=lambda p: _natural_sort_key(p.name),
        )

    for card_dir in card_dirs:
        num = card_dir.name
        result_data = _load_json(card_dir / "result.json")

        # Try external cards_dir first (for harvested runs), then local
        spec_data = None
        if cards_dir is not None:
            spec_data = _load_json(cards_dir / "sos" / num / "card_spec.json")
        if spec_data is None:
            spec_data = _load_json(card_dir / "card_spec.json")

        card_name = ""
        if spec_data and isinstance(spec_data, dict):
            card_name = spec_data.get("name", spec_data.get("card_name", ""))

        status = status_map.get(num, "completed")

        if status == "timeout":
            cards_timed_out += 1
        elif status == "no_output":
            cards_no_output += 1
        else:
            cards_completed += 1

        entry: dict = {
            "collector_number": num,
            "card_name": card_name,
            "status": status,
        }

        if result_data and isinstance(result_data, dict):
            passed = result_data.get("tests_passed", 0)
            total = result_data.get("tests_total", 0)
            failed = result_data.get("tests_failed", 0)
            entry["audited_passed"] = passed
            entry["audited_total"] = total
        else:
            passed = 0
            total = 0
            failed = 0
            entry["audited_passed"] = 0
            entry["audited_total"] = 0

        per_card.append(entry)

    # ---- Merge status.json entries that lack directories ----
    seen_nums = {d.name for d in card_dirs}
    for num, st in status_map.items():
        if num not in seen_nums:
            if st == "timeout":
                cards_timed_out += 1
            elif st == "no_output":
                cards_no_output += 1
            else:
                cards_completed += 1
            per_card.append({
                "collector_number": num,
                "card_name": "",
                "status": st,
                "audited_passed": 0,
                "audited_total": 0,
            })

    # ---- Use eval_result.json for accurate aggregation if available ----
    if eval_result and isinstance(eval_result, dict):
        sos_results = eval_result.get("sos_results", {})
        fdn_results = eval_result.get("fdn_results", {})
        engine_result = eval_result.get("engine_result", {})

        for _k, cr in sos_results.items():
            if isinstance(cr, dict):
                p = cr.get("tests_passed", 0)
                t = cr.get("tests_total", 0)
                sos_total_passed += p
                sos_total_tests += t
                sos_cards_completed += 1
                if t > 0 and p == t:
                    sos_cards_all_pass += 1

        for _k, cr in fdn_results.items():
            if isinstance(cr, dict):
                p = cr.get("tests_passed", 0)
                t = cr.get("tests_total", 0)
                fdn_total_passed += p
                fdn_total_tests += t
                fdn_cards_total += 1
                if t > 0 and p == t:
                    fdn_cards_all_pass += 1

        engine_passed = engine_result.get("tests_passed", 0) if isinstance(engine_result, dict) else 0
        engine_total = engine_result.get("tests_total", 0) if isinstance(engine_result, dict) else 0
    else:
        # Fall back to per-card directory data for SOS
        for card_dir in card_dirs:
            result_data = _load_json(card_dir / "result.json")
            if result_data and isinstance(result_data, dict):
                p = result_data.get("tests_passed", 0)
                t = result_data.get("tests_total", 0)
                sos_total_passed += p
                sos_total_tests += t
                sos_cards_completed += 1
                if t > 0 and p == t:
                    sos_cards_all_pass += 1
        engine_passed = 0
        engine_total = 0

    # ---- Compute rates ----
    audited_pass_rate = (
        sos_total_passed / sos_total_tests if sos_total_tests > 0 else 0.0
    )
    card_pass_rate = (
        sos_cards_all_pass / sos_cards_completed
        if sos_cards_completed > 0
        else 0.0
    )
    fdn_test_pass_rate = (
        fdn_total_passed / fdn_total_tests if fdn_total_tests > 0 else 0.0
    )
    fdn_card_pass_rate = (
        fdn_cards_all_pass / fdn_cards_total if fdn_cards_total > 0 else 0.0
    )
    engine_test_pass_rate = (
        engine_passed / engine_total if engine_total > 0 else 0.0
    )

    total_card_count = cards_completed + cards_no_output + cards_timed_out
    if total_card_count == 0:
        total_card_count = len(per_card)

    # ---- Read timeout_seconds from run manifest, else default ----
    manifest = _load_json(run_dir / "run_manifest.json") or {}
    timeout_seconds = manifest.get("timeout_seconds", 7200)

    summary: dict = {
        "docker_image": image_name,
        "run_metadata": {
            "image": image_name,
            "timestamp": _parse_timestamp_from_dirname(run_dir),
            "card_count": total_card_count,
            "timeout_seconds": timeout_seconds,
            "harness_version": _get_harness_version(),
        },
        "sos_card_correctness": {
            "audited_pass_rate": round(audited_pass_rate, 4),
            "card_pass_rate": round(card_pass_rate, 4),
            "cards_completed": cards_completed,
            "cards_no_output": cards_no_output,
            "cards_timed_out": cards_timed_out,
        },
        "fdn_regression": {
            "fdn_test_pass_rate": round(fdn_test_pass_rate, 4),
            "fdn_card_pass_rate": round(fdn_card_pass_rate, 4),
        },
        "engine_regression": {
            "engine_test_pass_rate": round(engine_test_pass_rate, 4),
            "engine_churn_lines": _count_engine_churn_lines(run_dir),
        },
        "per_card": per_card,
    }

    if run_status is not None:
        summary["run_status"] = run_status
    if wall_clock_seconds is not None:
        summary["wall_clock_seconds"] = round(wall_clock_seconds, 3)
    if resumed_from is not None:
        summary["resumed_from"] = resumed_from
    if resumed_image_changed is not None:
        summary["resumed_image_changed"] = resumed_image_changed

    # Write to run_dir/run_summary.json
    summary_path = run_dir / "run_summary.json"
    try:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write run_summary.json: %s", exc)

    return summary


def _natural_sort_key(name: str) -> tuple:
    """Sort key that handles numeric directory names naturally."""
    try:
        return (0, int(name))
    except ValueError:
        return (1, name)
