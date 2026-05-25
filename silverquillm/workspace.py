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

__all__ = ["stage_workspace"]

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
You are expected to make changes to the engine to implement new mechanics. The existing \
code base may not be perfect, you are free to make changes that don't break current behavior.

Do not modify any files under workspace/tests/engine/. These tests are staged for your \
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
