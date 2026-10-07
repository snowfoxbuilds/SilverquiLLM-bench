"""The environment unit tests build runs in: no grader Docker, and a clean run provenance.

Unit tests grade toy benchmarks from temporary bench roots, so the rule that the imported
package is the bench root's own is lifted too; ``tests/test_karn_results_sharing.py``
exercises it directly.

The suite's autouse fixtures apply it to every unit test; a module-scoped fixture that builds
runs once applies it itself (``tests/retained_runs.py``).
"""

from __future__ import annotations

import pytest

#: The provenance a clean run records; unit tests run from checkouts with work in progress.
CLEAN_PROVENANCE = {
    "host_label": "test-host",
    "host_label_source": "env",
    "bench": {"commit": "0" * 40, "dirty": False},
    "benchmark_root": {"commit": "0" * 40, "dirty": False},
    "recipe_revision": "1" * 40,
    "allow_dirty": False,
    "dirty_reasons": [],
}


def refuse_grader_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests inject ``tests.grader_fixtures.local_grader()``; only integration tests reach Docker."""
    from silverquillm.karn import grader

    def refuse(*args, **kwargs):
        raise AssertionError("unit test reached the grader's Docker client; inject local_grader()")

    for name in ("run", "image_id", "image_python", "build", "remove"):
        monkeypatch.setattr(grader.DockerRunner, name, refuse)


def record_clean_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs record a clean provenance instead of inspecting this checkout.

    ``tests/test_karn_provenance.py`` exercises the real rule directly.
    """
    from silverquillm.karn import execution

    monkeypatch.setattr(
        execution,
        "collect_provenance",
        lambda labels, bench_root, *, allow_dirty: {**CLEAN_PROVENANCE, "allow_dirty": allow_dirty},
    )


def accept_any_bench_root(monkeypatch: pytest.MonkeyPatch) -> None:
    from silverquillm.karn import provenance

    monkeypatch.setattr(provenance, "require_package_from", lambda bench_root: None)


def apply(monkeypatch: pytest.MonkeyPatch) -> None:
    refuse_grader_docker(monkeypatch)
    record_clean_provenance(monkeypatch)
    accept_any_bench_root(monkeypatch)
