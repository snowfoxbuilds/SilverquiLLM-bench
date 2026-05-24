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
from pathlib import Path

import click

__all__ = ["stage_workspace"]

# ---------------------------------------------------------------------------
# Repo root — resolved once at import time
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PROMPT_TEXT = """\
Implement all SOS cards in `/workspace/cards/sos/`. Each card directory contains \
a `card_spec.json` with the card's details and a `card_impl.py` template to fill in.
Use the completed FDN cards in `/workspace/cards/fdn/` as implementation examples. \
Refer to `rules_overview.md` for a compact rules skim (always read first) and \
`rulebook.md` for the full deep-reference rules text.
For engine API discovery, read the source modules directly — they have rich docstrings: \
`engine/card.py`, `engine/events.py`, `engine/triggers.py`, \
`engine/replacement_effects.py`, `engine/zones.py`.
You are expected to make changes to the engine to implement new mechanics. The existing \
code base may not be perfect, you are free to make changes that don't break current behavior.

Maintain `/workspace/decisions.md` as you work. For each card you attempt, add a section \
documenting non-obvious implementation choices and anything you punted on. Use this format:

```
# Decisions
## {card_id} {Card Name}
- Needed: <what the card requires mechanically>.
- <what you did and why — especially reuse of existing APIs or workarounds>.
- BLOCKED: <anything you know is wrong or incomplete but had no better option>.
```

Every card you attempt must have an entry. This is your structured record of *why* you \
made each choice and *what you know you punted on*.

Do not modify any files under workspace/tests/engine/. These tests are staged for your \
local verification only; the runner uses its own authoritative copies for grading. \
Modifying the workspace tests will not change your score — it will only mislead you \
about whether your engine changes are correct.
"""

# ---------------------------------------------------------------------------
# Reference doc locations (relative to repo root)
# ---------------------------------------------------------------------------

_REFERENCE_DOCS = {
    "test_utils.md": "benchmarks/sos/workspace/tests/test_utils.md",
}

_RULEBOOK_SRC = "benchmarks/sos/data/comprehensive_rules.txt"
_RULES_OVERVIEW_SRC = "benchmarks/sos/data/rules_overview.md"


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
    cards_dir = _REPO_ROOT / "cards"
    engine_dir = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "engine"
    workspace = output_dir / "workspace"
    output = output_dir / "output"

    # Clean stale artifacts from previous runs
    if workspace.exists():
        shutil.rmtree(workspace)
    if output.exists():
        shutil.rmtree(output)

    workspace.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    # --- prompt.md ---
    prompt_text = _prompt_text(card_filter)
    (workspace / "prompt.md").write_text(prompt_text, encoding="utf-8")

    # Echo the card filter
    click.echo(f"Card filter: {card_filter or 'all'}")

    # --- engine/ (full copy) ---
    _copy_engine(engine_dir, workspace / "engine")

    # --- reference docs ---
    _copy_reference_docs(workspace)

    # --- decisions.md (empty template for agent to fill) ---
    (workspace / "decisions.md").write_text(
        "# Decisions\n", encoding="utf-8"
    )

    # --- tests/engine/ (staged per ADR-006) ---
    _stage_engine_tests(workspace)

    # --- cards/ ---
    _stage_cards(cards_dir, workspace / "cards", card_filter=card_filter)

    return workspace, output


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _copy_engine(engine_dir: Path, dest: Path) -> None:
    """Copy the full engine source tree, skipping __pycache__."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        engine_dir,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _stage_engine_tests(workspace: Path) -> None:
    """Stage engine regression tests into workspace/tests/engine/ (ADR-006)."""
    src = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "tests" / "engine"
    if not src.exists():
        return
    dest = workspace / "tests" / "engine"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _copy_reference_docs(workspace: Path) -> None:
    """Copy reference docs into the workspace root."""
    for dest_name, rel_src in _REFERENCE_DOCS.items():
        src = _REPO_ROOT / rel_src
        if not src.exists():
            raise FileNotFoundError(
                f"Reference doc source not found: {src}"
            )
        shutil.copy2(src, workspace / dest_name)

    # rulebook.md — hard error if missing
    rulebook_src = _REPO_ROOT / _RULEBOOK_SRC
    if not rulebook_src.exists():
        raise FileNotFoundError(
            f"Rulebook source not found: {rulebook_src}"
        )
    shutil.copy2(rulebook_src, workspace / "rulebook.md")

    # rules_overview.md — hard error if missing
    overview_src = _REPO_ROOT / _RULES_OVERVIEW_SRC
    if not overview_src.exists():
        raise FileNotFoundError(
            f"Rules overview source not found: {overview_src}"
        )
    shutil.copy2(overview_src, workspace / "rules_overview.md")


def _prompt_text(card_filter: list[str] | None) -> str:
    """Return prompt text, adjusting for card filter if set."""
    if card_filter is not None:
        cards_list = ", ".join(card_filter)
        return _PROMPT_TEXT.replace(
            "Implement all SOS cards",
            f"Implement the following SOS cards: {cards_list}",
        )
    return _PROMPT_TEXT


def _stage_cards(
    cards_dir: Path,
    dest_cards: Path,
    *,
    card_filter: list[str] | None = None,
) -> None:
    """Copy fdn/ and sos/ card directories into workspace/cards/.

    When *card_filter* is set, only SOS cards whose collector number is in
    the filter list are staged.  FDN cards are always staged in full.
    """
    for tier in ("fdn", "sos"):
        src_tier = cards_dir / tier
        if not src_tier.exists():
            continue

        dest_tier = dest_cards / tier
        dest_tier.mkdir(parents=True, exist_ok=True)

        # Copy shared helper files at the tier level (.py files, excluding __pycache__)
        for f in sorted(src_tier.iterdir()):
            if f.is_file() and f.suffix == ".py":
                shutil.copy2(f, dest_tier / f.name)

        # Copy per-card directories
        for card_dir in sorted(src_tier.iterdir()):
            if not card_dir.is_dir():
                continue
            if card_dir.name == "__pycache__":
                continue
            # Only copy directories that have card_spec.json
            spec_file = card_dir / "card_spec.json"
            impl_file = card_dir / "card_impl.py"
            if not spec_file.exists():
                continue

            # Apply card_filter for SOS tier only
            if tier == "sos" and card_filter is not None:
                spec_data = json.loads(spec_file.read_text(encoding="utf-8"))
                cn = str(spec_data.get("collector_number", ""))
                # Normalize: strip leading zeros for numeric values
                cn_norm = str(int(cn)) if cn.isdigit() else cn
                filter_norm = {str(int(f)) if f.isdigit() else f for f in card_filter}
                if cn_norm not in filter_norm:
                    continue

            dest_card = dest_cards / tier / card_dir.name
            dest_card.mkdir(parents=True, exist_ok=True)

            shutil.copy2(spec_file, dest_card / "card_spec.json")
            if impl_file.exists():
                shutil.copy2(impl_file, dest_card / "card_impl.py")
