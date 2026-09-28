from __future__ import annotations

import fcntl
import hashlib
import io
import shutil
import stat
import subprocess
import threading
import zipfile
from pathlib import Path

import pytest

from silverquillm.karn.definition import KarnError, canonical, load_candidate
from silverquillm.karn.host import DockerHost
from silverquillm.karn.toolchain import (
    TOOLCHAIN_SOURCE,
    TOOLCHAIN_TARGET,
    locked_wheels,
    prepare_toolchain,
    read_pins,
)

from .test_karn_host import FakeDocker, make_candidate

GRADER_REQUIREMENTS = TOOLCHAIN_SOURCE.parent / "grader_image/requirements.txt"


def vendored_copy(tmp_path) -> Path:
    source = tmp_path / "toolchain-source"
    shutil.copytree(TOOLCHAIN_SOURCE, source)
    return source


def write_wheel(path: Path, members: dict[str, bytes], *, mode: int = stat.S_IFREG | 0o644):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = mode << 16
            archive.writestr(info, content)
    path.write_bytes(buffer.getvalue())


def replace_pytest_timeout(source: Path, members: dict[str, bytes], **options) -> None:
    """Swap in a crafted pytest-timeout wheel and re-pin it, so only its members are at fault."""
    wheel = source / "wheels/pytest_timeout-2.4.0-py3-none-any.whl"
    write_wheel(wheel, members, **options)
    repin(source, wheel)


def repin(source: Path, wheel: Path) -> None:
    sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
    requirements = source / "requirements.txt"
    lines = requirements.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("pytest-timeout=="))
    lines[start + 1 : start + 3] = [f"    --hash=sha256:{sha}"]
    requirements.write_text("\n".join(lines) + "\n")


def test_toolchain_pins_match_the_graders_where_they_overlap():
    toolchain = read_pins(TOOLCHAIN_SOURCE / "requirements.txt")
    grader = read_pins(GRADER_REQUIREMENTS)
    shared = set(toolchain) & set(grader)
    assert {"pytest", "pluggy", "iniconfig", "packaging", "pygments"} <= shared
    assert {name: toolchain[name] for name in shared} == {name: grader[name] for name in shared}
    assert "pytest-timeout" in toolchain


def test_vendored_wheels_are_pure_python_and_match_their_pins():
    wheels = locked_wheels()
    assert {wheel.path.name.split("-")[0] for wheel in wheels} == {
        "iniconfig",
        "packaging",
        "pluggy",
        "pygments",
        "pytest",
        "pytest_timeout",
    }


def test_prepare_unpacks_once_and_reuses_a_verified_tree(tmp_path):
    first = prepare_toolchain(tmp_path / "state")
    assert (first.path / "pytest/__init__.py").is_file()
    assert (first.path / "pytest_timeout.py").is_file()
    assert first.path.stat().st_mode & 0o777 == 0o755
    marker = first.path / "pytest/__init__.py"
    before = marker.stat().st_mtime_ns
    second = prepare_toolchain(tmp_path / "state")
    assert second == first
    assert marker.stat().st_mtime_ns == before
    assert first.to_dict() == {"digest": first.digest, "target": TOOLCHAIN_TARGET}


def test_a_tampered_unpacked_tree_is_rebuilt(tmp_path):
    toolchain = prepare_toolchain(tmp_path / "state")
    (toolchain.path / "pytest/__init__.py").write_text("raise SystemExit('tampered')")
    rebuilt = prepare_toolchain(tmp_path / "state")
    assert "tampered" not in (rebuilt.path / "pytest/__init__.py").read_text()


def test_a_wheel_whose_hash_does_not_match_is_refused(tmp_path):
    source = vendored_copy(tmp_path)
    wheel = source / "wheels/pluggy-1.6.0-py3-none-any.whl"
    wheel.write_bytes(wheel.read_bytes() + b"\0")
    with pytest.raises(KarnError, match="test_toolchain_integrity_mismatch:pluggy"):
        prepare_toolchain(tmp_path / "state", source)
    assert not (tmp_path / "state/toolchains").exists()


@pytest.mark.parametrize(
    "change",
    [
        lambda wheels: (wheels / "pluggy-1.6.0-py3-none-any.whl").unlink(),
        lambda wheels: shutil.copy(
            wheels / "pluggy-1.6.0-py3-none-any.whl", wheels / "extra-1.0-py3-none-any.whl"
        ),
        lambda wheels: (wheels / "pluggy-1.6.0-py3-none-any.whl").rename(
            wheels / "pluggy-1.6.0-cp313-cp313-linux_x86_64.whl"
        ),
    ],
    ids=["missing", "unpinned", "platform"],
)
def test_the_wheel_set_must_equal_the_pins(tmp_path, change):
    source = vendored_copy(tmp_path)
    change(source / "wheels")
    with pytest.raises(KarnError, match="test_toolchain_integrity_mismatch"):
        locked_wheels(source)


@pytest.mark.parametrize(
    ("members", "mode"),
    [
        ({"../escape.py": b""}, stat.S_IFREG | 0o644),
        ({"/absolute.py": b""}, stat.S_IFREG | 0o644),
        ({"link.py": b"/etc/passwd"}, stat.S_IFLNK | 0o777),
        ({"pytest_timeout-2.4.0.data/scripts/run": b""}, stat.S_IFREG | 0o755),
    ],
    ids=["traversal", "absolute", "symlink", "data-dir"],
)
def test_unsafe_wheel_members_are_refused_even_when_pinned(tmp_path, members, mode):
    source = vendored_copy(tmp_path)
    replace_pytest_timeout(source, members, mode=mode)
    with pytest.raises(KarnError, match="test_toolchain_integrity_mismatch:pytest_timeout"):
        prepare_toolchain(tmp_path / "state", source)
    assert not (tmp_path / "escape.py").exists()


@pytest.mark.parametrize(
    ("members", "error"),
    [
        ({"pytest_timeout.py": b"x", "pytest_timeout.py/": b""}, "FileExistsError"),
        ({"pytest_timeout.py": b"x", "pytest_timeout.py/inner.py": b""}, "FileExistsError"),
    ],
    ids=["duplicate", "file-then-directory"],
)
def test_clashing_members_refuse_instead_of_crashing(tmp_path, members, error):
    source = vendored_copy(tmp_path)
    replace_pytest_timeout(source, members)
    with pytest.raises(KarnError, match=f"integrity_mismatch:pytest_timeout.*:{error}"):
        prepare_toolchain(tmp_path / "state", source)


def test_a_pinned_wheel_with_a_bad_crc_is_refused(tmp_path):
    source = vendored_copy(tmp_path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("pytest_timeout.py", b"original content")
    damaged = buffer.getvalue().replace(b"original content", b"tampered content")
    wheel = source / "wheels/pytest_timeout-2.4.0-py3-none-any.whl"
    wheel.write_bytes(damaged)
    repin(source, wheel)
    with pytest.raises(KarnError, match="integrity_mismatch:pytest_timeout.*:BadZipFile"):
        prepare_toolchain(tmp_path / "state", source)


def test_unpacking_uses_the_bytes_that_were_hashed(tmp_path, monkeypatch):
    source = vendored_copy(tmp_path)
    wheels = locked_wheels(source)
    for wheel in wheels:
        wheel.path.write_bytes(b"swapped after hashing")
    monkeypatch.setattr("silverquillm.karn.toolchain.locked_wheels", lambda _source: wheels)
    toolchain = prepare_toolchain(tmp_path / "state", source)
    assert (toolchain.path / "pytest/__init__.py").is_file()


def test_prepare_waits_for_the_host_lock(tmp_path):
    root = tmp_path / "state/toolchains"
    root.mkdir(parents=True)
    finished = threading.Event()
    with open(root / ".lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        worker = threading.Thread(
            target=lambda: (prepare_toolchain(tmp_path / "state"), finished.set())
        )
        worker.start()
        assert not finished.wait(0.5)
    worker.join(30)
    assert finished.is_set()


def test_concurrent_runs_rebuild_a_corrupted_tree_once_without_crashing(tmp_path):
    first = prepare_toolchain(tmp_path / "state")
    (first.path / "pytest/__init__.py").write_text("corrupted")
    results, errors = [], []

    def prepare():
        try:
            results.append(prepare_toolchain(tmp_path / "state"))
        except Exception as error:  # noqa: BLE001 -- collected for the assertion below.
            errors.append(error)

    workers = [threading.Thread(target=prepare) for _ in range(6)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(60)
    assert errors == []
    assert results == [first] * 6
    assert "corrupted" not in (first.path / "pytest/__init__.py").read_text()


def with_runtime(candidate, **changes):
    candidate.runtime.update(changes)
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    return load_candidate(candidate.build_output, "bare", image_inspector=lambda ref: {"Id": ref})


@pytest.fixture(scope="module")
def toolchain(tmp_path_factory):
    """One unpacked toolchain for the host tests, which only mount it."""
    return prepare_toolchain(tmp_path_factory.mktemp("state"))


def run_with_toolchain(tmp_path, candidate, toolchain, docker=None):
    docker = docker or FakeDocker()
    result = DockerHost(docker=docker).run(
        candidate, tmp_path / "workspace", tmp_path / "run", "task", test_toolchain=toolchain
    )
    create = next(command for command in docker.commands if command[0] == "create")
    return result, create, toolchain


def environment_of(create) -> dict:
    values = [create[i + 1] for i, word in enumerate(create) if word == "--env"]
    return dict(value.split("=", 1) for value in values)


def test_host_mounts_the_toolchain_read_only_and_puts_it_first_on_pythonpath(tmp_path, toolchain):
    result, create, toolchain = run_with_toolchain(tmp_path, make_candidate(tmp_path), toolchain)
    assert result.status == "completed", result.to_dict()
    assert f"type=bind,src={toolchain.path},dst={TOOLCHAIN_TARGET},readonly" in create
    assert environment_of(create)["PYTHONPATH"] == TOOLCHAIN_TARGET
    recorded = result.host_configuration
    assert recorded["test_toolchain"] == {
        "digest": toolchain.digest,
        "target": TOOLCHAIN_TARGET,
        "python_path": TOOLCHAIN_TARGET,
    }
    assert [mount["target"] for mount in recorded["mounts"]] == [TOOLCHAIN_TARGET]


def test_construct_pythonpath_is_kept_after_the_toolchain(tmp_path, toolchain):
    candidate = with_runtime(
        make_candidate(tmp_path), environment={"PYTHONPATH": "/opt/construct/lib"}
    )

    class ImageDocker(FakeDocker):
        def inspect_image(self, reference):
            return {"Id": reference, "Config": {"Env": ["PYTHONPATH=/image/lib"]}}

    _, create, _ = run_with_toolchain(tmp_path, candidate, toolchain, ImageDocker())
    assert environment_of(create)["PYTHONPATH"] == TOOLCHAIN_TARGET + ":/opt/construct/lib"


def test_image_pythonpath_is_kept_when_the_construct_sets_none(tmp_path, toolchain):
    class ImageDocker(FakeDocker):
        def inspect_image(self, reference):
            return {"Id": reference, "Config": {"Env": ["PATH=/usr/bin", "PYTHONPATH=/image/lib"]}}

    _, create, _ = run_with_toolchain(tmp_path, make_candidate(tmp_path), toolchain, ImageDocker())
    assert environment_of(create)["PYTHONPATH"] == TOOLCHAIN_TARGET + ":/image/lib"


def test_toolchain_may_not_overlap_a_definition_mount(tmp_path, toolchain):
    candidate = make_candidate(tmp_path)
    mounts = candidate.runtime["mounts"]
    mounts[0]["target"] = "/run/silverquillm"
    candidate = with_runtime(candidate, mounts=mounts)
    docker = FakeDocker()
    with pytest.raises(KarnError, match="infrastructure_mount_shadows_definition"):
        DockerHost(docker=docker).run(
            candidate,
            tmp_path / "workspace",
            tmp_path / "run",
            "task",
            test_toolchain=toolchain,
        )
    assert docker.commands == []


def test_toolchain_may_not_overlap_a_plugin_or_telemetry_mount(tmp_path, toolchain):
    # CODEX_HOME inside the toolchain puts the bench's own telemetry mount under its target,
    # the same late-arriving shape as a plugin-admitted mount.
    candidate = with_runtime(
        make_candidate(tmp_path), environment={"CODEX_HOME": TOOLCHAIN_TARGET + "/native"}
    )
    docker = FakeDocker()
    result = DockerHost(docker=docker).run(
        candidate,
        tmp_path / "workspace",
        tmp_path / "run",
        "task",
        test_toolchain=toolchain,
        runtime_config="[otel]\n",
    )
    assert result.status == "host_failed"
    assert result.error == "infrastructure_mount_overlaps"
    assert not docker.created


@pytest.mark.parametrize(
    "home",
    ["/run/silverquillm/native/../test-toolchain", "//run/silverquillm/test-toolchain"],
    ids=["dotdot", "double-slash"],
)
def test_a_noncanonical_telemetry_target_cannot_hide_under_the_toolchain(tmp_path, toolchain, home):
    # Docker cleans both shapes to a path under the toolchain; pathlib compares them as disjoint.
    candidate = with_runtime(make_candidate(tmp_path), environment={"CODEX_HOME": home})
    docker = FakeDocker()
    result = DockerHost(docker=docker).run(
        candidate,
        tmp_path / "workspace",
        tmp_path / "run",
        "task",
        test_toolchain=toolchain,
        runtime_config="[otel]\n",
    )
    assert result.status == "host_failed"
    assert result.error == "noncanonical_mount_target"
    assert not docker.created


@pytest.fixture
def local_image():
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", "python:3.13-slim"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("requires local python:3.13-slim image; tests never pull")
    return result.stdout.strip()


@pytest.mark.integration
def test_real_docker_candidate_runs_pytest_from_the_mounted_toolchain(
    tmp_path, local_image, toolchain
):
    command = (
        "import pathlib, subprocess, sys;"
        "pathlib.Path('/workspace/test_ok.py').write_text('def test_ok():\\n    pass\\n');"
        "out = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider',"
        " '/workspace/test_ok.py'], capture_output=True, text=True, cwd='/workspace');"
        "pathlib.Path('/workspace/pytest.out').write_text(out.stdout + out.stderr);"
        "sys.exit(out.returncode)"
    )
    candidate = make_candidate(tmp_path, image=local_image, main=["python3", "-c", command])
    result = DockerHost().run(
        candidate,
        tmp_path / "workspace",
        tmp_path / "run",
        "task",
        budget_seconds=60,
        test_toolchain=toolchain,
    )
    output = (tmp_path / "workspace/pytest.out").read_text()
    assert result.status == "completed", output
    assert "plugins: timeout-2.4.0" in output and "1 passed" in output
