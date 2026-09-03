"""Guard: the oracle workspace's audited tests and skills must stay in sync
with their canonical copies.

Two copies of each per-card audited ``tests.py`` exist:

  * canonical / scoring:   ``benchmarks/sos/data/tests/audited/<set>/<cn>/tests.py``
  * oracle-validation:     ``benchmarks/sos/data/test_oracle_workspace/tests/audited/<set>/<cn>/tests.py``

The oracle copy is a *subset* (only the cards that have reference solutions), but
every file it contains must be byte-identical to its canonical counterpart. When
the two drift, the reference solutions get validated against stale tests — e.g.
``sos_257`` once froze on an older "add {C}" spec while the canonical tests had
moved on to "add one mana of any color", making the (correct) reference appear to
fail 3/13. This test makes that kind of drift fail loudly.

The oracle workspace also mirrors the agent workspace's ``skills/`` subtree:

  * canonical:   ``benchmarks/sos/workspace/skills/<skill>/SKILL.md``
  * oracle:      ``benchmarks/sos/data/test_oracle_workspace/skills/<skill>/SKILL.md``

The two workspaces share a byte-identical ``AGENTS.md`` that links into
``skills/`` (the grep-rulebook skill), so every skill file present in the agent
workspace must exist, byte-identical, in the oracle workspace — otherwise that
shared link dangles in the oracle copy. This guard makes a missing or drifted
skill file fail loudly, so the mirror stays whole and the AGENTS.md link resolves.

To resync a drifted file, copy the canonical version over the oracle one (the
failure message prints the exact command).
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CANONICAL_AUDITED = _REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited"
_ORACLE_AUDITED = (
    _REPO_ROOT
    / "benchmarks"
    / "sos"
    / "data"
    / "test_oracle_workspace"
    / "tests"
    / "audited"
)
_CANONICAL_SKILLS = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "skills"
_ORACLE_SKILLS = (
    _REPO_ROOT / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "skills"
)


def _oracle_test_files() -> list[Path]:
    """Every per-card ``tests.py`` shipped in the oracle workspace audited tree.

    ``rglob("tests.py")`` matches only the per-card test modules (named exactly
    ``tests.py``); harness modules like ``test_api_conformance.py`` and
    ``conftest.py`` — which intentionally differ between the two trees — are not
    matched and so are not compared.
    """
    return sorted(_ORACLE_AUDITED.rglob("tests.py"))


def _rel_id(path: Path) -> str:
    return str(path.relative_to(_ORACLE_AUDITED))


def test_oracle_audited_tree_is_nonempty() -> None:
    """Guard against the sync check silently passing on zero files."""
    assert _oracle_test_files(), (
        f"No per-card tests.py found under {_ORACLE_AUDITED} — the sync guard "
        "would be vacuous. Did the oracle workspace layout change?"
    )


@pytest.mark.parametrize("oracle_path", _oracle_test_files(), ids=_rel_id)
def test_oracle_audited_test_matches_canonical(oracle_path: Path) -> None:
    """Each oracle audited ``tests.py`` is byte-identical to its canonical copy."""
    rel = oracle_path.relative_to(_ORACLE_AUDITED)
    canonical_path = _CANONICAL_AUDITED / rel

    assert canonical_path.exists(), (
        f"Oracle audited test {rel} has no canonical counterpart at "
        f"{canonical_path.relative_to(_REPO_ROOT)} — every oracle test must "
        "mirror a canonical scoring test."
    )

    if oracle_path.read_bytes() == canonical_path.read_bytes():
        return

    diff = "".join(
        difflib.unified_diff(
            canonical_path.read_text().splitlines(keepends=True),
            oracle_path.read_text().splitlines(keepends=True),
            fromfile=f"canonical/{rel}",
            tofile=f"oracle/{rel}",
        )
    )
    pytest.fail(
        f"Oracle audited test {rel} has drifted from its canonical copy.\n"
        f"Resync with:\n"
        f"  cp {canonical_path.relative_to(_REPO_ROOT)} \\\n"
        f"     {oracle_path.relative_to(_REPO_ROOT)}\n\n"
        f"{diff}"
    )


def _canonical_skill_files() -> list[Path]:
    """Every file shipped under the agent workspace's ``skills/`` subtree."""
    return sorted(p for p in _CANONICAL_SKILLS.rglob("*") if p.is_file())


def _skill_rel_id(path: Path) -> str:
    return str(path.relative_to(_CANONICAL_SKILLS))


def test_canonical_skills_tree_is_nonempty() -> None:
    """Guard against the skills mirror silently passing on zero files."""
    assert _canonical_skill_files(), (
        f"No skill files found under {_CANONICAL_SKILLS} — the skills mirror "
        "guard would be vacuous. Did the workspace layout change?"
    )


@pytest.mark.parametrize("canonical_path", _canonical_skill_files(), ids=_skill_rel_id)
def test_oracle_skill_mirrors_canonical_workspace(canonical_path: Path) -> None:
    """Each agent-workspace skill file exists byte-identical in the oracle
    workspace, so the shared AGENTS.md's ``skills/`` link resolves there too."""
    rel = canonical_path.relative_to(_CANONICAL_SKILLS)
    oracle_path = _ORACLE_SKILLS / rel

    assert oracle_path.exists(), (
        f"Skill file {rel} is present in the agent workspace but missing from "
        f"the oracle workspace at {oracle_path.relative_to(_REPO_ROOT)} — the "
        "shared AGENTS.md links into skills/, so the oracle mirror must carry "
        f"it.\nAdd it with:\n"
        f"  cp {canonical_path.relative_to(_REPO_ROOT)} \\\n"
        f"     {oracle_path.relative_to(_REPO_ROOT)}"
    )

    if oracle_path.read_bytes() == canonical_path.read_bytes():
        return

    diff = "".join(
        difflib.unified_diff(
            canonical_path.read_text().splitlines(keepends=True),
            oracle_path.read_text().splitlines(keepends=True),
            fromfile=f"canonical/{rel}",
            tofile=f"oracle/{rel}",
        )
    )
    pytest.fail(
        f"Oracle skill {rel} has drifted from its canonical workspace copy.\n"
        f"Resync with:\n"
        f"  cp {canonical_path.relative_to(_REPO_ROOT)} \\\n"
        f"     {oracle_path.relative_to(_REPO_ROOT)}\n\n"
        f"{diff}"
    )
