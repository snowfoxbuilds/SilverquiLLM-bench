"""Local Docker and installed-wheel integration; no live inference or user credentials."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from silverquillm.karn.batching import KarnScheduler
from silverquillm.karn.definition import canonical, digest, load_candidate
from silverquillm.karn.docker import RUN_LABEL
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.grader import grader_tag
from silverquillm.karn.host import DockerHost
from silverquillm.karn.login_pool import LoginPool
from silverquillm.results_repo import iter_run_records

from .scheduler_fixtures import ThreadWorker
from .test_karn_execution import benchmark_data
from .test_karn_host import FIXTURES, make_candidate
from .test_karn_observations import journal, otlp, record

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def grader_image():
    checked = subprocess.run(
        ["docker", "image", "inspect", grader_tag("3.13")], capture_output=True, check=False
    )
    if checked.returncode:
        pytest.skip(
            "requires the grader image; run `silverquillm grader build --python 3.13` first"
        )
    return json.loads(checked.stdout)[0]["Id"]


@pytest.fixture
def python_image(grader_image):
    checked = subprocess.run(
        ["docker", "image", "inspect", "python:3.13-slim"], capture_output=True, check=False
    )
    if checked.returncode:
        pytest.skip("requires already available python:3.13-slim; tests do not pull")
    return json.loads(checked.stdout)[0]["Id"]


def invoke(*args):
    installed = os.environ.get("SILVERQUILLM_TEST_INSTALLED_CLI")
    command = (
        [installed]
        if installed
        else [
            sys.executable,
            "-I",
            "-c",
            f"import sys; sys.path.insert(0, {str(REPO)!r}); from silverquillm.cli import main; main()",
        ]
    )
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [*command, *args],
        cwd="/tmp",
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )


@pytest.mark.integration
@pytest.mark.parametrize("benchmark", ["smoke", "hob-medium"])
def test_direct_and_batch_cli_retain_all_three_dimensions(tmp_path, python_image, benchmark):
    candidate = make_candidate(
        tmp_path,
        image=python_image,
        main=[
            "python3",
            "-c",
            (
                "import json,os; from pathlib import Path; root=Path('/workspace'); "
                "[(root/path).write_text(content) for path,content in json.loads(os.environ.get('KARN_TEST_IMPLEMENTATIONS','{}')).items()]; "
                "(root/'integration-marker').write_text('executed')"
            ),
        ],
    )
    if benchmark == "smoke":
        selected = json.loads((REPO / "benchmarks/smoke/config.json").read_text())["cards"]
        reference = {
            f"cards/fdn/fdn_{number}/card_impl.py": (
                REPO / "benchmarks/hob-medium/workspace/cards/fdn" / f"fdn_{number}/card_impl.py"
            ).read_text()
            for number in selected
        }
        candidate.runtime["environment"]["KARN_TEST_IMPLEMENTATIONS"] = json.dumps(reference)
        candidate.definition_path.write_bytes(canonical(candidate.definition))
        candidate = load_candidate(candidate.build_output, "bare")
    # The fixture uses a local Python image without a committed Karn recipe.
    common = [
        "--allow-dirty",
        "--bench-root",
        str(REPO),
        "--results-dir",
        str(tmp_path / "runs"),
        "--results-repo",
        str(tmp_path / "records"),
        "--state-root",
        str(tmp_path / "state"),
    ]
    direct = invoke(
        "run",
        "--build-output",
        str(candidate.build_output),
        "--construct",
        "bare",
        "--benchmark",
        benchmark,
        "--budget-seconds",
        "20",
        *common,
    )
    assert direct.returncode == 0, direct.stderr + direct.stdout[-3000:]
    batches = tmp_path / "batches"
    batches.mkdir()
    (batches / "sample.toml").write_text(
        'format = "karn-v5"\n[[runs]]\nbuild_output = '
        + json.dumps(str(candidate.build_output))
        + '\nconstruct = "bare"\nbenchmark = '
        + json.dumps(benchmark)
        + "\nbudget_seconds = 20\n"
    )
    queued = invoke(
        "scheduler",
        "--batches-dir",
        str(batches),
        "--once",
        "--replay-without-state",
        "sample",
        *common,
    )
    assert queued.returncode == 0, queued.stderr + queued.stdout
    assert "1 run(s) executed" in queued.stdout
    records = list(iter_run_records(tmp_path / "records"))
    assert len(records) == 2
    reference_scores = records[0][1].scores
    for _, result in records:
        assert result.benchmark == benchmark
        assert result.run_metadata["execution"]["status"] == "completed"
        assert all(
            score["evaluated"] and score["tests_total"] > 0 for score in result.scores.values()
        ), result.scores
        # The benchmark retains known defects; direct and queued grades must agree.
        for dimension in ("fdn_regression", "engine_regression"):
            assert (
                result.scores[dimension]["tests_passed"],
                result.scores[dimension]["tests_total"],
            ) == (
                reference_scores[dimension]["tests_passed"],
                reference_scores[dimension]["tests_total"],
            ), result.scores[dimension]
        assert result.run_metadata["measurements"]["estimated_cost"]["value"] is None
        assert (tmp_path / "runs" / result.run_id / "workspace_final/integration-marker").exists()
        config = json.loads((REPO / "benchmarks" / benchmark / "config.json").read_text())
        assert len(result.scores["card_correctness"]["coverage"]["population_cards"]) == len(
            config["cards"]
        )
        source = REPO / "benchmarks" / benchmark
        population = {
            path.name
            for path in (source / "workspace/cards/fdn").iterdir()
            if (path / "card_spec.json").is_file()
        }
        covered = {
            path.name
            for path in (source / "data/tests/audited/fdn").iterdir()
            if (path / "tests.py").is_file()
        }
        if config["draft_set"]["primary_set_code"] == "FDN":
            # FDN targets are scored in card correctness.
            targets = {f"fdn_{number}" for number in config["cards"]}
            population -= targets
            covered -= targets
        coverage = result.scores["fdn_regression"]["coverage"]
        assert set(coverage["population_cards"]) == population
        assert set(coverage["evaluated_cards"]) == covered
        assert set(coverage["uncovered_cards"]) == population - covered


@pytest.mark.integration
def test_default_docker_relay_records_turns_cost_and_login_persistence(tmp_path, python_image):
    native_lines = journal(model="gpt-6-astra") + [
        record(
            "response_item",
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "exec_command",
                "arguments": "not retained",
            },
        )
    ]
    payload = otlp(name="codex.tool_result", call_id="call-1", success="false")
    command = """import json,pathlib,os,tomllib,urllib.request
home=pathlib.Path(os.environ['CODEX_HOME'])
sessions=home/'sessions'; sessions.mkdir()
(sessions/'rollout-synthetic.jsonl').write_text(LINES)
endpoint=tomllib.loads((home/'config.toml').read_text())['otel']['exporter']['otlp-http']['endpoint']
request=urllib.request.Request(endpoint,data=json.dumps(PAYLOAD).encode(),headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(request,timeout=5) as response:
    assert response.status==200
""".replace("LINES", repr("\n".join(native_lines) + "\n")).replace("PAYLOAD", repr(payload))
    candidate = make_candidate(
        tmp_path,
        image=python_image,
        main=["python3", "-c", command],
        network={"mode": "restricted", "https_hosts": []},
    )
    shutil.copytree(FIXTURES / "login-build/plugins", candidate.build_output / "plugins")
    manifest = json.loads(
        (candidate.build_output / "plugins/karn-codex-login-0.1.0/install.json").read_text()
    )["manifest"]
    candidate.runtime["plugins"] = [
        {
            "id": manifest["id"],
            "version": manifest["version"],
            "source": "catalog",
            "artifact": digest(canonical(manifest, ascii_only=True)),
        }
    ]
    candidate.runtime["environment"]["CODEX_HOME"] = "/native"
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    candidate = load_candidate(candidate.build_output, "bare")
    state = tmp_path / "state"
    profile = LoginPool.of(state, "karn-codex-login").named_slot("bare")
    auth = canonical(
        {
            "tokens": {
                key: "synthetic-" + key
                for key in ("access_token", "refresh_token", "id_token", "account_id")
            }
        }
    )
    profile.set_secret(
        "login.bare",
        canonical(
            {
                "format": 1,
                "revision": "a" * 32,
                "files": {"auth.json": base64.b64encode(auth).decode()},
            }
        ).decode(),
    )
    result = run_benchmark(
        build_output=candidate.build_output,
        construct="bare",
        benchmark_id="example",
        bench_root=benchmark_data(tmp_path / "data"),
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=state,
        budget_seconds=20,
    )
    assert result.run_metadata["execution"]["status"] == "completed", result.run_metadata
    observations = result.run_metadata["measurements"]
    assert observations["agent_turns"]["responses"]["value"] == 1
    assert observations["agent_turns"]["tool_calls"]["value"] == 1
    assert observations["agent_turns"]["total"]["value"] == 2
    assert float(observations["estimated_cost"]["value"]) > 0
    assert observations["coverage"]["observed_threads"] == 1
    assert not (profile.state / "work").exists()
    assert json.loads(profile.get_secret("login.bare"))["revision"] != "a" * 32
    assert all(score["evaluated"] for score in result.scores.values())


@pytest.mark.integration
def test_batch_recovers_a_live_orphan_and_grades_partial_work_without_replay(
    tmp_path, python_image
):
    candidate = make_candidate(
        tmp_path,
        image=python_image,
        main=[
            "python3",
            "-c",
            "from pathlib import Path; import time; Path('/workspace/partial-marker').write_text('one execution'); time.sleep(60)",
        ],
    )
    root = benchmark_data(tmp_path / "data")
    batches = tmp_path / "batches"
    batches.mkdir()
    (batches / "interrupted.toml").write_text(
        'format="karn-v5"\n[[runs]]\nbuild_output='
        + json.dumps(str(candidate.build_output))
        + '\nconstruct="bare"\nbenchmark="example"\nbudget_seconds=60\n'
    )

    class AbandonedHost(DockerHost):
        def run(self, selected, workspace, evidence_dir, prompt, **kwargs):
            name = "sq-run-" + kwargs["run_id"]
            self.docker.command(
                "create",
                "--pull",
                "never",
                "--name",
                name,
                "--label",
                RUN_LABEL + "=" + kwargs["run_id"],
                "--network",
                "none",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--mount",
                f"type=bind,src={workspace},dst=/workspace",
                "--entrypoint",
                "python3",
                selected.image_id,
                *selected.runtime["main"][1:],
            )
            self.docker.command("start", name)
            deadline = time.monotonic() + 5
            while not (workspace / "partial-marker").exists():
                if time.monotonic() > deadline:
                    raise AssertionError("fixture workload did not start")
                time.sleep(0.05)
            raise SystemExit(91)

    host = AbandonedHost()
    launches = []

    def execute(**kwargs):
        launches.append(kwargs["run_id"])
        return run_benchmark(**kwargs, host=host)

    scheduler = KarnScheduler(
        batches,
        worker_factory=ThreadWorker,
        bench_root=root,
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
        replay_without_state=["interrupted"],
        executor=execute,
    )
    try:
        with pytest.raises(SystemExit):
            scheduler.run_until_idle()
        assert host.docker.inspect_container("sq-run-" + launches[0])["State"]["Running"]
        assert scheduler.run_until_idle() == 0
        assert len(launches) == 1
        result = next(iter_run_records(tmp_path / "records"))[1]
        assert result.run_metadata["execution"]["status"] == "interrupted"
        assert result.run_metadata["execution"]["workspace_stopped"]
        assert all(score["pass_rate"] == 1 for score in result.scores.values())
        assert (
            tmp_path / "runs" / launches[0] / "workspace_final/partial-marker"
        ).read_text() == "one execution"
        assert host.docker.inspect_container("sq-run-" + launches[0]) is None
    finally:
        for run_id in launches:
            host.docker.remove("sq-run-" + run_id)
