"""The real grader container: parity with host grading and the sandbox boundary (ADR-013)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from silverquillm.evaluator import evaluate_run
from silverquillm.karn.benchmark import load_benchmark
from silverquillm.karn.grader import ContainerGrader

from . import test_karn_end_to_end as end_to_end
from .test_karn_execution import benchmark_data
from .test_karn_host import make_candidate

REPO, invoke = end_to_end.REPO, end_to_end.invoke
grader_image, python_image = end_to_end.grader_image, end_to_end.python_image


def outcomes(result):
    cards = {
        name: (
            card.tests_passed,
            card.tests_total,
            sorted((node["test_node"], node["outcome"]) for node in card.test_nodes),
        )
        for dimension in (result.sos_results, result.fdn_results)
        for name, card in dimension.items()
    }
    engine = result.engine_result
    return cards, (engine.tests_passed, engine.tests_total)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("benchmark_id", "source", "target"),
    [
        ("smoke", "workspace", None),
        ("hob-medium", "data/test_oracle_workspace", (69, 69)),
        ("hob-medium", "workspace", (14, 69)),
    ],
)
def test_container_grading_reproduces_host_grading(
    tmp_path,
    grader_image,
    benchmark_id,
    source,
    target,
):
    benchmark = load_benchmark(REPO, benchmark_id)
    workspace = benchmark.root / source
    contained = ContainerGrader(grader_image).evaluate_run(
        tmp_path, benchmark, workspace_source=workspace
    )
    direct = evaluate_run(tmp_path, benchmark, workspace_source=workspace)
    assert outcomes(contained) == outcomes(direct)
    if target is not None:
        passed = sum(card.tests_passed for card in contained.sos_results.values())
        total = sum(card.tests_total for card in contained.sos_results.values())
        assert (passed, total) == target


HOSTILE_ENGINE = """
import os, socket
from pathlib import Path

ATTEMPTS = {}

def _attempt(name, action):
    try:
        action()
        ATTEMPTS[name] = "allowed"
    except OSError:
        ATTEMPTS[name] = "denied"

_attempt("login_state", lambda: os.listdir(__STATE__))
_attempt("host_file", lambda: Path(__CANARY__).read_text())
_attempt("network", lambda: socket.create_connection(("1.1.1.1", 443), timeout=3).close())
_attempt("package_write", lambda: Path("/opt/sq/silverquillm/planted.py").write_text("x"))
_attempt("workspace_write", lambda: Path("/grade/workspace/planted.py").write_text("x"))
_attempt("root_write", lambda: Path("/planted").write_text("x"))
ATTEMPTS["operator_environment"] = "denied" if "SQ_CANARY" not in os.environ else "allowed"
"""


@pytest.mark.integration
def test_hostile_engine_is_contained_and_grading_still_completes(
    tmp_path,
    grader_image,
    monkeypatch,
):
    canary = tmp_path / "host-canary.txt"
    canary.write_text("host-only")
    monkeypatch.setenv("SQ_CANARY", "operator-secret")
    root = benchmark_data(tmp_path / "data")
    workspace = root / "benchmarks/example/workspace"
    (workspace / "engine/__init__.py").write_text(
        HOSTILE_ENGINE.replace(
            "__STATE__", repr(str(Path.home() / ".local/state/silverquillm"))
        ).replace("__CANARY__", repr(str(canary)))
    )
    (workspace / "engine_tests/test_contained.py").write_text(
        "import engine\n"
        "def test_every_escape_was_denied():\n"
        "    assert set(engine.ATTEMPTS.values()) == {'denied'}, engine.ATTEMPTS\n"
    )
    benchmark = load_benchmark(root, "example")
    grader = ContainerGrader(grader_image)
    assert grader.engine_health(workspace) == {"usable": True, "reason": None}
    result = grader.evaluate_run(tmp_path, benchmark, workspace_source=workspace)
    assert result.engine_result.tests_total == 2
    assert result.engine_result.tests_passed == 2, result.engine_result.errors
    assert not (REPO / "silverquillm/planted.py").exists()
    assert not (workspace / "planted.py").exists()


@pytest.mark.integration
def test_run_refuses_before_launch_without_the_grader_image(tmp_path, python_image):
    candidate = make_candidate(tmp_path, image=python_image)
    runs = tmp_path / "runs"
    result = invoke(
        "run",
        "--build-output",
        str(candidate.build_output),
        "--construct",
        "bare",
        "--benchmark",
        "smoke",
        "--bench-root",
        str(REPO),
        "--results-dir",
        str(runs),
        "--results-repo",
        str(tmp_path / "records"),
        "--state-root",
        str(tmp_path / "state"),
        "--grader-image",
        "silverquillm-grader:absent-" + uuid.uuid4().hex,
    )
    assert result.returncode != 0
    assert "grader_image_unavailable" in result.stderr
    assert not runs.exists()
