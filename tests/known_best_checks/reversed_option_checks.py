"""Known-Best's FDN Audited Tests hold however the engine orders a question's
options: an engine offers its options in any stable order (ADR-017), so a
script that names only a printed class while two objects carry it must say
which object it means, or it passes only under the order Known-Best happens
to use.

Every FDN Audited suite is rerun with each question's options reversed.
Demolition Field's suite, where two Fields carry the same abilities, also runs
under both orders here, with a check that a script naming only the ability
class fails once the order is reversed.

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest
from cards.fdn.fdn_687.card_impl import DemolitionFieldAbility2
from test_interface import PlayDiverged, Zone

from silverquillm.table import moves, on_stack

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO / "known_best/workspace"
AUDITED_FDN = REPO / "known_best/data/tests/audited/fdn"
FIELD_SUITE = AUDITED_FDN / "fdn_687/tests.py"
TWO_FIELDS = ("TestDemolitionFieldAbility", "test_an_illegal_target_on_resolution_means_no_search")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reverse_options = _load(Path(__file__).parent / "reversed_options.py", "reversed_options").reverse_options
FIELD = _load(FIELD_SUITE, "demolition_field_audited")
FIELD_CASES = [
    (cls.__name__, name)
    for _, cls in inspect.getmembers(FIELD, inspect.isclass)
    if cls.__module__ == FIELD.__name__ and cls.__name__.startswith("Test")
    for name, _ in inspect.getmembers(cls, inspect.isfunction)
    if name.startswith("test_")
]


def _run(case):
    cls, name = case
    getattr(getattr(FIELD, cls)(), name)()


def test_every_fdn_audited_case_holds_with_every_question_reversed():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(AUDITED_FDN), "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
         "-p", "reversed_options", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (Path(__file__).parent, WORKSPACE, REPO))),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]


def test_the_field_suite_has_every_case():
    assert len(FIELD_CASES) == 8
    assert TWO_FIELDS in FIELD_CASES


@pytest.mark.parametrize("order", ["as offered", "reversed"])
@pytest.mark.parametrize("case", FIELD_CASES, ids=lambda c: f"{c[0]}.{c[1]}")
def test_field_case_holds_in_either_order(case, order, monkeypatch):
    if order == "reversed":
        reverse_options(monkeypatch)
    _run(case)


def _class_only(t, field, target):
    t.act(0, DemolitionFieldAbility2, choices=[target],
          then=[moves(field, Zone.GRAVEYARD), on_stack(DemolitionFieldAbility2, 0)])


def test_naming_only_the_ability_class_activates_whichever_field_comes_first(monkeypatch):
    """With the activation named by class alone, the reversed order activates
    the second Field, so the view expecting the first one in the graveyard
    diverges: the check can tell a bound script from an unbound one."""
    monkeypatch.setattr(FIELD, "_activate", _class_only)
    _run(TWO_FIELDS)
    reverse_options(monkeypatch)
    with pytest.raises(PlayDiverged):
        _run(TWO_FIELDS)
