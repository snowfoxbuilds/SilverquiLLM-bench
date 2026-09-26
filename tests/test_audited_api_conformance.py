"""CI gate for the audited-test API conformance scan.

The scanner itself lives in the oracle workspace
(``benchmarks/sos/data/test_oracle_workspace/tests/audited/
test_api_conformance.py`` — single source of truth); this wrapper loads it by
path and re-exposes its meta-tests so the repo-level ``pytest tests/`` run
(the CI gate) enforces conformance.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from scripts.oracle_support import check_v2_api, load_layout

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFORMANCE_PATH = (
    _REPO_ROOT
    / "benchmarks"
    / "sos"
    / "data"
    / "test_oracle_workspace"
    / "tests"
    / "audited"
    / "test_api_conformance.py"
)


def _load_conformance_module():
    spec = importlib.util.spec_from_file_location("_audited_api_conformance", _CONFORMANCE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass processing can resolve the module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_conformance = _load_conformance_module()


def test_audited_tests_use_only_the_test_api() -> None:
    """Every audited test file conforms to the AUDITED-TEST-API allow-list."""
    _conformance.test_audited_tests_use_only_the_test_api()


def test_checker_catches_planted_violations(tmp_path: Path) -> None:
    """The conformance guard is demonstrably red on a planted violation."""
    _conformance.test_checker_catches_planted_violations(tmp_path)


def test_checker_passes_clean_canonical_shape(tmp_path: Path) -> None:
    """The canonical simulation-only test shape produces zero violations."""
    _conformance.test_checker_passes_clean_canonical_shape(tmp_path)


_V2_LAYOUT = load_layout(_REPO_ROOT, "hob-medium", require_cards=True)
_V2_SUITES = sorted((_V2_LAYOUT.benchmark_root / "data/tests/audited").rglob("tests.py"))
_V2_SUITES += sorted((_V2_LAYOUT.oracle / "tests/audited").rglob("tests.py"))


@pytest.mark.parametrize(
    "path", _V2_SUITES, ids=lambda p: str(p.relative_to(_V2_LAYOUT.benchmark_root))
)
def test_v2_audits_use_canonical_public_gameplay(path):
    assert not check_v2_api(path, _V2_LAYOUT), "\n".join(check_v2_api(path, _V2_LAYOUT))


def test_v2_host_helpers_import_only_canonical_engine_symbols():
    issues = check_v2_api(_V2_LAYOUT.oracle / "test_utils.py", _V2_LAYOUT, helper=True)
    assert not issues, "\n".join(issues)


@pytest.mark.parametrize(
    "source",
    [
        "from engine.events import AbilityActivatedTriggeredEvent as event\n",
        "import engine.hob_support as helpers\n",
        "from engine.game_state import _TURN_SEQUENCE as order\n",
        "def test_bad(card,game):\n    run = card.on_resolve\n    run(game)\n",
        "from builtins import getattr as read\ndef test_bad(card):\n    read(card, '_marker')\n",
        "def test_bad(game):\n    game.trigger_manager.fire_event(object())\n",
    ],
)
def test_v2_checker_rejects_aliases_and_oracle_dependencies(source, tmp_path):
    path = tmp_path / "bad.py"
    path.write_text(source)
    assert check_v2_api(path, _V2_LAYOUT)


def test_v2_checker_accepts_public_actions_and_fixture_hooks(tmp_path):
    path = tmp_path / "clean.py"
    path.write_text(
        "from engine.card import Instant\nfrom engine.game import destroy as destroy_permanent\nclass Fixture(Instant):\n    def on_resolve(self, game):\n        destroy_permanent(game, self.target)\ndef test_action(game, card):\n    destroy_permanent(game, card)\n"
    )
    assert not check_v2_api(path, _V2_LAYOUT)


def test_v2_checker_validates_helper_imports_too(tmp_path):
    path = tmp_path / "test_utils.py"
    path.write_text("from engine.hob_support import delayed\n")
    assert check_v2_api(path, _V2_LAYOUT, helper=True)
