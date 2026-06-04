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

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFORMANCE_PATH = (
    _REPO_ROOT
    / "benchmarks" / "sos" / "data" / "test_oracle_workspace"
    / "tests" / "audited" / "test_api_conformance.py"
)


def _load_conformance_module():
    spec = importlib.util.spec_from_file_location(
        "_audited_api_conformance", _CONFORMANCE_PATH
    )
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
