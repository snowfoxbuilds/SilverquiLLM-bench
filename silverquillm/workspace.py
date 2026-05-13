"""Workspace staging for Docker-based agent runs.

Builds the workspace directory that gets mounted into a Docker container.
The workspace is the agent's entire world — contamination control is enforced
by what gets staged here.

Public API
----------
- ``stage_workspace`` — build workspace + output directories, return their paths.
"""

from __future__ import annotations

import shutil
from pathlib import Path

__all__ = ["stage_workspace"]

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PROMPT_TEXT = """\
Implement all SOS cards in `/workspace/cards/sos/`. Each card directory contains \
a `card_spec.json` with the card's details and a `card_impl.py` template to fill in.
Use the completed FDN cards in `/workspace/cards/fdn/` as implementation examples. \
Refer to `rulebook.md` for detailed game rules and `engine_api.md` for the engine API.
"""

# ---------------------------------------------------------------------------
# Reference doc locations (relative to repo root)
# ---------------------------------------------------------------------------

_REFERENCE_DOCS = {
    "engine_api.md": "docs/engine_api.md",
    "test_utils.md": "docs/test_utils.md",
    "base_classes.py": "engine/card.py",
}

# rulebook.md has a separate path because it may not exist yet
_RULEBOOK_SRC = "docs/rulebook.md"


def stage_workspace(
    cards_dir: Path,
    engine_dir: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Build the workspace directory tree for a Docker agent run.

    Parameters
    ----------
    cards_dir:
        Repo ``cards/`` directory containing ``fdn/`` and ``sos/`` sub-dirs.
    engine_dir:
        Repo ``engine/`` directory (full engine source).
    output_dir:
        Parent directory where ``workspace/`` and ``output/`` are created.

    Returns
    -------
    tuple[Path, Path]
        ``(workspace_path, output_path)`` — both guaranteed to exist.
    """
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
    (workspace / "prompt.md").write_text(_PROMPT_TEXT, encoding="utf-8")

    # --- engine/ (full copy) ---
    _copy_engine(engine_dir, workspace / "engine")

    # --- reference docs ---
    _copy_reference_docs(cards_dir, engine_dir, workspace)

    # --- cards/ ---
    _stage_cards(cards_dir, workspace / "cards")

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


def _copy_reference_docs(cards_dir: Path, engine_dir: Path, workspace: Path) -> None:
    """Copy reference docs into the workspace root."""
    # Resolve repo root from cards_dir (cards/ sits at repo root)
    repo_root = cards_dir.parent

    for dest_name, rel_src in _REFERENCE_DOCS.items():
        # Use engine_dir for base_classes.py instead of hardcoded repo path
        if dest_name == "base_classes.py":
            src = engine_dir / "card.py"
        else:
            src = repo_root / rel_src
        if src.exists():
            shutil.copy2(src, workspace / dest_name)
        else:
            # Create a stub so the agent still has the file
            (workspace / dest_name).write_text(
                f"# {dest_name}\n\nStub — source not found at {rel_src}.\n",
                encoding="utf-8",
            )

    # rulebook.md
    rulebook_src = repo_root / _RULEBOOK_SRC
    if rulebook_src.exists():
        shutil.copy2(rulebook_src, workspace / "rulebook.md")
    else:
        (workspace / "rulebook.md").write_text(
            "# Rulebook\n\nStub — rulebook not yet generated.\n",
            encoding="utf-8",
        )


def _stage_cards(cards_dir: Path, dest_cards: Path) -> None:
    """Copy fdn/ and sos/ card directories into workspace/cards/."""
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

            dest_card = dest_cards / tier / card_dir.name
            dest_card.mkdir(parents=True, exist_ok=True)

            shutil.copy2(spec_file, dest_card / "card_spec.json")
            if impl_file.exists():
                shutil.copy2(impl_file, dest_card / "card_impl.py")
