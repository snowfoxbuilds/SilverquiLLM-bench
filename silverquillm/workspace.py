"""Workspace staging for Docker-based agent runs.

Builds the workspace directory that gets mounted into a Docker container.
The workspace is the agent's entire world — contamination control is enforced
by what gets staged here.

Public API
----------
- ``stage_workspace`` — build workspace + output directories, return their paths.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import click

__all__ = [
    "stage_workspace",
    "stage_workspace_from_prior_run",
    "build_resume_preamble",
]

# ---------------------------------------------------------------------------
# Repo root — resolved once at import time
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Benchmark set configuration
# ---------------------------------------------------------------------------

_BENCHMARK_SET_NAME = "sos"  # module-level; promote to CLI flag when adding a second target set

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PROMPT_TEXT = """\
Implement all SOS cards in `/workspace/cards/sos/`. Each card directory contains \
a `card_spec.json` with the card's details and a `card_impl.py` template to fill in.
Use the completed FDN cards in `/workspace/cards/fdn/` as implementation examples. \
Refer to `RULEBOOK.txt` for the full deep-reference rules text.
For engine API discovery, read the source modules directly — they have rich docstrings: \
`engine/card.py`, `engine/events.py`, `engine/triggers.py`, \
`engine/replacement_effects.py`, `engine/zones.py`.
You are expected to make changes to the engine to implement new keywords and mechanics. The existing \
code base may not be perfect, you are free to make changes that don't break current behavior.

Do not modify any files under workspace/engine_tests/. These tests are staged for your \
local verification only; the runner uses its own authoritative copies for grading. \
Modifying the workspace tests will not change your score — it will only mislead you \
about whether your engine changes are correct.
"""


def stage_workspace(
    output_dir: Path,
    *,
    card_filter: list[str] | None = None,
) -> tuple[Path, Path]:
    """Build the workspace directory tree for a Docker agent run.

    Parameters
    ----------
    output_dir:
        Parent directory where ``workspace/`` and ``output/`` are created.
    card_filter:
        Optional list of collector numbers to include for SOS cards.
        When ``None``, all SOS cards are staged.  FDN cards are always
        staged in full regardless of this parameter.

    Returns
    -------
    tuple[Path, Path]
        ``(workspace_path, output_path)`` — both guaranteed to exist.
    """
    src = _REPO_ROOT / "benchmarks" / _BENCHMARK_SET_NAME / "workspace"
    workspace = output_dir / "workspace"
    output = output_dir / "output"

    if not src.is_dir() or not any(src.iterdir()):
        raise FileNotFoundError(
            f"Benchmark workspace directory missing or empty: {src}"
        )

    if workspace.exists():
        shutil.rmtree(workspace)
    if output.exists():
        shutil.rmtree(output)

    shutil.copytree(src, workspace, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    output.mkdir(parents=True, exist_ok=True)

    (workspace / "prompt.md").write_text(_prompt_text(card_filter), encoding="utf-8")
    (workspace / "run_manifest.json").write_text(
        json.dumps({"benchmark_set": _BENCHMARK_SET_NAME, "cards": card_filter}, indent=2), encoding="utf-8"
    )
    click.echo(f"Card filter: {card_filter or 'all'}")

    if card_filter is not None:
        _apply_card_filter(workspace / "cards" / "sos", card_filter)

    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
    subprocess.run(
        ["git", "-c", "user.name=runner", "-c", "user.email=runner@silverquillm",
         "commit", "-q", "-m", "initial workspace"],
        cwd=workspace, check=True,
    )

    return workspace, output


# ---------------------------------------------------------------------------
# Resume staging variant
# ---------------------------------------------------------------------------


def stage_workspace_from_prior_run(
    output_dir: Path,
    prior_run_dir: Path,
    *,
    prompt_text: str,
    run_manifest: dict,
) -> tuple[Path, Path]:
    """Build the workspace tree for a Resume Leg by copying a prior run's
    ``workspace_final/`` wholesale.

    Differences from :func:`stage_workspace`:

    - Source is ``prior_run_dir / "workspace_final/"`` instead of the bench
      repo's canonical workspace.
    - Prior ``.git`` history is preserved verbatim — no ``git init`` and no
      seed commit.
    - Only ``prompt.md`` and ``run_manifest.json`` are overwritten. Every
      other file (including agent-prompt-layer tracking files like
      ``KEY_DECISIONS.md`` / ``RUN_DECISIONS.md`` / ``MODEL_AUDIT.jsonl`` /
      ``FILES_MODIFIED.json``, if present) is carried over byte-for-byte.

    Parameters
    ----------
    output_dir:
        Parent directory where ``workspace/`` and ``output/`` are created.
    prior_run_dir:
        Path to the prior run's results directory (must contain
        ``workspace_final/.git/``).
    prompt_text:
        The full ``prompt.md`` body to write — typically the canonical User
        Prompt with a Resume Preamble prepended.
    run_manifest:
        Dict to serialize as ``run_manifest.json`` for this Resume Leg.

    Returns
    -------
    tuple[Path, Path]
        ``(workspace_path, output_path)``.
    """
    src = prior_run_dir / "workspace_final"
    if not src.is_dir():
        raise FileNotFoundError(
            f"Prior run has no workspace_final/ at {src}"
        )
    if not (src / ".git").is_dir():
        raise FileNotFoundError(
            f"Prior workspace_final/ has no .git history at {src}"
        )

    workspace = output_dir / "workspace"
    output = output_dir / "output"

    if workspace.exists():
        shutil.rmtree(workspace)
    if output.exists():
        shutil.rmtree(output)

    # copytree preserves .git/ and every tracking file the prior run
    # accumulated. No ignore patterns — we want byte-for-byte continuity.
    shutil.copytree(src, workspace)
    output.mkdir(parents=True, exist_ok=True)

    # Refresh per-run files only. Do NOT touch agent-prompt-layer tracking
    # files (KEY_DECISIONS.md, MODEL_AUDIT.jsonl, FILES_MODIFIED.json,
    # RUN_DECISIONS.md); they hold prior-session state.
    (workspace / "prompt.md").write_text(prompt_text, encoding="utf-8")
    (workspace / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8"
    )

    return workspace, output


# ---------------------------------------------------------------------------
# Resume Preamble
# ---------------------------------------------------------------------------


def build_resume_preamble(
    prior_run_id: str,
    *,
    snapshot_fallback_used: bool = False,
    snapshot_utc: str | None = None,
    image_changed: bool = False,
    prior_image: str | None = None,
    new_image: str | None = None,
    filter_mismatch: bool = False,
    prior_card_filter: list[str] | None = None,
    new_card_filter: list[str] | None = None,
    missing_summary: bool = False,
) -> str:
    """Return the image-agnostic Resume Preamble block.

    Placed at the top of ``prompt.md`` under a ``## Resume context`` heading
    and followed by a ``---`` separator and the original User Prompt body.

    Conditional disclosure lines are appended only when the corresponding
    flag is set; the always-included base block tells the agent that this
    is a resume of ``<prior-run-id>``, that prior tests/implementations may
    already exist, that the workspace ``.git`` records prior commits, and
    that it should inspect current state before doing new work.
    """
    lines: list[str] = ["## Resume context", ""]
    lines.append(
        f"This is a Resume Leg of prior Benchmark Run `{prior_run_id}`."
    )
    lines.append(
        "Prior tests and card implementations may already exist in this "
        "workspace; the `.git` history records earlier commits made during "
        "the prior run. Inspect the current workspace state (`git log`, "
        "`git status`, existing files under `cards/sos/` and `engine/`) "
        "before doing new work — duplicating prior effort wastes budget."
    )

    if snapshot_fallback_used:
        when = f" (snapshot from {snapshot_utc})" if snapshot_utc else ""
        lines.append(
            f"- Snapshot fallback was used to harvest the prior run{when}. "
            "The workspace you inherit was rolled back to the last viable "
            "engine snapshot; it is NOT where the prior agent stopped. Some "
            "work performed after that snapshot was not preserved."
        )

    if image_changed:
        prior = f"`{prior_image}`" if prior_image else "a different image"
        current = f"`{new_image}`" if new_image else "the current image"
        lines.append(
            f"- This leg is running under {current}, but the prior leg used "
            f"{prior}. Workspace tracking files (e.g. agent-internal "
            "decision logs) may follow the prior agent's conventions; treat "
            "them as informational rather than authoritative."
        )

    if filter_mismatch:
        prior_fmt = (
            ",".join(prior_card_filter) if prior_card_filter else "all cards"
        )
        new_fmt = (
            ",".join(new_card_filter) if new_card_filter else "all cards"
        )
        lines.append(
            f"- This leg's card filter ({new_fmt}) differs from the prior "
            f"leg's filter ({prior_fmt}). Prior-implemented cards that lie "
            "outside this leg's filter are inherited workspace state, not "
            "part of this leg's scope — do not redo them, but do not score "
            "them either."
        )

    if missing_summary:
        lines.append(
            "- The prior run's `run_summary.json` was missing or "
            "unreadable; some prior-run metadata could not be carried "
            "forward into this preamble. Treat the inherited workspace as "
            "the source of truth."
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _prompt_text(card_filter: list[str] | None) -> str:
    """Return prompt text, adjusting for card filter if set."""
    if card_filter is not None:
        cards_list = ", ".join(card_filter)
        return _PROMPT_TEXT.replace(
            "Implement all SOS cards",
            f"Implement the following SOS cards: {cards_list}",
        )
    return _PROMPT_TEXT


def _apply_card_filter(sos_dir: Path, card_filter: list[str]) -> None:
    """Remove SOS card directories not matching the filter.

    Normalizes collector numbers (strips leading zeros) for comparison.
    """
    if not sos_dir.exists():
        return

    filter_norm = {str(int(f)) if f.isdigit() else f for f in card_filter}

    for card_dir in sorted(sos_dir.iterdir()):
        if not card_dir.is_dir():
            continue
        if card_dir.name == "__pycache__":
            shutil.rmtree(card_dir)
            continue
        spec_file = card_dir / "card_spec.json"
        if not spec_file.exists():
            continue
        spec_data = json.loads(spec_file.read_text(encoding="utf-8"))
        cn = str(spec_data.get("collector_number", ""))
        cn_norm = str(int(cn)) if cn.isdigit() else cn
        if cn_norm not in filter_norm:
            shutil.rmtree(card_dir)
