"""Tests for the replay registry loader (silverquillm/replay/registry_loader.py).

The loader imports a workspace's card implementations via flat ``from engine...``
/ ``from cards...`` imports, which bind to whichever workspace is first on
``sys.path``. The root test suite already puts the *SOS* workspace on sys.path
(see tests/conftest.py), so building the *MSH* registry in-process would bind the
wrong engine. These tests therefore run the loader in a **subprocess** with only
the chosen workspace selected — exactly how the real CLI runs it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MSH_WORKSPACE = REPO / "benchmarks" / "msh" / "workspace"

_SNIPPET = r"""
import json, sys
sys.path.insert(0, {repo!r})
from silverquillm.replay.registry_loader import build_registry

reg, rep = build_registry({ws!r}, "fdn")
names = reg.list_all()
known = ["Sire of Seven Deaths", "Healer's Hawk", "Fleeting Flight"]
basics = ["Plains", "Island", "Swamp", "Mountain", "Forest"]
out = {{
    "registered": rep.registered,
    "basic_lands": rep.basic_lands_registered,
    "size": len(reg),
    "n_skipped_import_error": len(rep.skipped_import_error),
    "n_skipped_no_class": len(rep.skipped_no_class),
    "n_collisions": len(rep.collisions),
    "known_present": [k for k in known if k in reg],
    "known_instantiable": [k for k in known if reg.create_instance(k).name == k],
    "basics_present": [b for b in basics if b in reg],
    "workspace": rep.workspace,
    "set_code": rep.set_code,
}}
print("JSON_START" + json.dumps(out) + "JSON_END")
"""


@pytest.fixture(scope="module")
def loaded() -> dict:
    """Build the FDN registry once, in an isolated interpreter."""
    if not MSH_WORKSPACE.is_dir():
        pytest.skip("MSH workspace not present")
    snippet = _SNIPPET.format(repo=str(REPO), ws=str(MSH_WORKSPACE))
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert proc.returncode == 0, f"loader subprocess failed:\n{proc.stderr}"
    blob = proc.stdout[
        proc.stdout.index("JSON_START") + len("JSON_START") : proc.stdout.index("JSON_END")
    ]
    return json.loads(blob)


def test_builds_without_crashing_on_stubs(loaded: dict) -> None:
    """Unimplemented stubs (broken imports) are skipped, not fatal."""
    # The mere fact the subprocess returned 0 proves stubs didn't crash the
    # build; assert at least one was actually skipped so the path is exercised.
    assert loaded["n_skipped_import_error"] >= 1


def test_registers_substantial_card_set(loaded: dict) -> None:
    """The FDN set yields a large registry (guards against a silently-empty build)."""
    assert loaded["registered"] >= 250


def test_basic_lands_folded_in(loaded: dict) -> None:
    """All five basic lands are registered (so they don't read as MISSING_CARD)."""
    assert loaded["basic_lands"] == 5
    assert sorted(loaded["basics_present"]) == ["Forest", "Island", "Mountain", "Plains", "Swamp"]


def test_known_cards_resolve_to_real_impls(loaded: dict) -> None:
    """Subclass cards and make_vanilla-factory cards both register and instantiate."""
    assert loaded["known_present"] == ["Sire of Seven Deaths", "Healer's Hawk", "Fleeting Flight"]
    assert loaded["known_instantiable"] == loaded["known_present"]


def test_registry_size_within_expected_bounds(loaded: dict) -> None:
    """Size is the FDN impls plus up to five basics (some basics may overlap an
    FDN basic-land dir, e.g. Plains); collisions are deduped, never double-counted."""
    assert loaded["registered"] <= loaded["size"] <= loaded["registered"] + 5


def test_report_records_workspace_and_set(loaded: dict) -> None:
    assert loaded["set_code"] == "fdn"
    assert loaded["workspace"].endswith("benchmarks/msh/workspace")
