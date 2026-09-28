"""The unchanged karn-claude-login plugin under the same host contract as the Codex one."""

from __future__ import annotations

import base64
import json
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

from silverquillm.karn.definition import PluginArtifact, canonical, digest
from silverquillm.karn.login import (
    LOGIN_PLUGINS,
    NATIVE_PRESERVED,
    LoginProfile,
    PluginProcess,
    admit_plugin_mounts,
    install_plugin,
    preserve_pending_native,
)

FIXTURE = Path(__file__).parent / "fixtures/karn/login-build-claude/plugins/karn-claude-login-0.1.0"


def credentials(token="initial"):
    return canonical(
        {
            "claudeAiOauth": {
                "accessToken": token + "-access",
                "refreshToken": token + "-refresh",
                "expiresAt": 1790000000000,
                "scopes": ["user:inference"],
            }
        }
    )


def enrolled(profile):
    profile.set_secret(
        "login." + profile.name,
        canonical(
            {
                "format": 1,
                "revision": "b" * 32,
                "files": {".credentials.json": base64.b64encode(credentials()).decode()},
            }
        ).decode(),
    )


@pytest.fixture(scope="module")
def artifact():
    manifest = json.loads((FIXTURE / "install.json").read_text())["manifest"]
    row = {
        "id": manifest["id"],
        "version": manifest["version"],
        "source": "catalog",
        "artifact": digest(canonical(manifest, ascii_only=True)),
    }
    return PluginArtifact(
        row,
        manifest,
        FIXTURE / "install.json",
        tuple((FIXTURE / name, value) for name, value in manifest["wheels"].items()),
        None,
    )


@pytest.fixture(scope="module")
def plugin_python(artifact, tmp_path_factory):
    if sys.version_info[:2] != (3, 13):
        pytest.skip("The pinned Karn Plugin SDK requires CPython 3.13")
    return install_plugin(
        artifact, tmp_path_factory.mktemp("claude-plugin-cache"), python=sys.executable
    )


def test_the_host_runs_exactly_the_codex_and_claude_login_plugins():
    assert LOGIN_PLUGINS == {"karn-codex-login", "karn-claude-login"}


def test_real_plugin_projects_credentials_and_persists_refresh(tmp_path, artifact, plugin_python):
    profile = LoginProfile(tmp_path / "login", "bare-claude-haiku")
    enrolled(profile)
    output = tmp_path / "output"
    output.mkdir()
    mounts = [{"Type": "bind", "Source": str(output), "Target": "/output", "ReadOnly": False}]
    with profile.exclusive(), PluginProcess(artifact, plugin_python, profile) as plugin:
        delivered = admit_plugin_mounts(
            mounts, plugin.invoke("before_container_mount", "first", mounts), profile.state
        )
        native = Path(delivered[-1]["Source"])
        assert delivered[-1]["Target"] == "/native" and delivered[-1]["ReadOnly"] is False
        assert {p.name for p in native.iterdir()} == {".credentials.json"}
        assert stat.S_IMODE((native / ".credentials.json").stat().st_mode) == 0o600
        (native / ".credentials.json").write_bytes(credentials("refreshed"))
        (native / "projects").mkdir()
        plugin.invoke("after_container_exit", "first", delivered)
        assert not native.exists()
        second = plugin.invoke("before_container_mount", "second", mounts)
        native = Path(second[-1]["Source"])
        assert (native / ".credentials.json").read_bytes() == credentials("refreshed")
        plugin.invoke("after_container_exit", "second", second)


def test_setup_runs_claude_auth_login_in_an_isolated_config_dir(
    tmp_path, artifact, plugin_python, monkeypatch
):
    profile = LoginProfile(tmp_path / "login", "bare-claude-haiku")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cli = fake_bin / "claude"
    cli.write_text(
        "#!/usr/bin/env python3\nimport json, os, pathlib, sys\n"
        "assert sys.argv[1:] == ['auth', 'login'], sys.argv\n"
        "assert 'ANTHROPIC_API_KEY' not in os.environ\n"
        "p=pathlib.Path(os.environ['CLAUDE_CONFIG_DIR'])\n"
        "assert not list(p.iterdir())\n"
        f"(p/'.credentials.json').write_bytes({credentials('enrolled')!r})\n"
        "(p/'.claude.json').write_text(json.dumps({'hasCompletedOnboarding': True, "
        "'projects': {'private': 1}}))\n"
    )
    cli.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-reach-login")
    with profile.exclusive(), PluginProcess(artifact, plugin_python, profile) as plugin:
        assert plugin.setup() == 0
    saved = json.loads(profile.get_secret("login.bare-claude-haiku"))
    assert base64.b64decode(saved["files"][".credentials.json"]) == credentials("enrolled")
    assert json.loads(base64.b64decode(saved["files"][".claude.json"])) == {
        "hasCompletedOnboarding": True
    }


def test_a_pending_claude_run_keeps_its_transcripts_but_never_credentials(tmp_path):
    profile = LoginProfile(tmp_path / "login", "bare-claude-haiku")
    evidence = tmp_path / "run"
    evidence.mkdir()
    work = profile.state / "work"
    session = work / "projects" / "-workspace" / "session-1"
    (session / "subagents").mkdir(parents=True)
    (work / "projects/-workspace/session-1.jsonl").write_text("main\n")
    (session / "subagents/agent-a.jsonl").write_text("child\n")
    (session / "subagents/agent-a.meta.json").write_text("{}")
    (work / ".credentials.json").write_bytes(credentials())
    (profile.state / "mounted.json").write_text(json.dumps({"run_id": "run"}))
    profile.journal({"run_id": "run", "container_name": "c", "evidence_dir": str(evidence)})
    outcome = preserve_pending_native(profile, lambda *args: None)
    assert outcome == {"run_id": "run", "preserved": True, "reason": None}
    kept = evidence / NATIVE_PRESERVED
    assert sorted(p.relative_to(kept).as_posix() for p in kept.rglob("*") if p.is_file()) == [
        "projects/-workspace/session-1.jsonl",
        "projects/-workspace/session-1/subagents/agent-a.jsonl",
    ]


def test_a_linked_projects_tree_is_not_followed(tmp_path):
    profile = LoginProfile(tmp_path / "login", "bare-claude-haiku")
    evidence = tmp_path / "run"
    evidence.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.jsonl").write_text("host file")
    (profile.state / "work").mkdir(parents=True)
    (profile.state / "work/projects").symlink_to(outside)
    (profile.state / "mounted.json").write_text(json.dumps({"run_id": "run"}))
    profile.journal({"run_id": "run", "container_name": "c", "evidence_dir": str(evidence)})
    outcome = preserve_pending_native(profile, lambda *args: None)
    assert outcome["preserved"] is False
    assert not (evidence / NATIVE_PRESERVED).exists()


def candidate_with_plugins(tmp_path, *rows):
    from silverquillm.karn.definition import load_candidate

    from .test_karn_host import make_candidate

    candidate = make_candidate(tmp_path)
    shutil.copytree(FIXTURE.parent, candidate.build_output / "plugins")
    candidate.runtime["plugins"] = list(rows)
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    return load_candidate(candidate.build_output, "bare", image_inspector=lambda ref: {"Id": ref})


def claude_row():
    manifest = json.loads((FIXTURE / "install.json").read_text())["manifest"]
    return {
        "id": manifest["id"],
        "version": manifest["version"],
        "source": "catalog",
        "artifact": digest(canonical(manifest, ascii_only=True)),
    }


def test_the_host_admits_the_claude_login_plugin_and_then_needs_a_profile(tmp_path):
    from silverquillm.karn.host import DockerHost

    from .test_karn_host import FakeDocker

    candidate = candidate_with_plugins(tmp_path, claude_row())
    docker = FakeDocker()
    result = DockerHost(docker=docker).run(candidate, tmp_path / "ws", tmp_path / "run", "task")
    assert (result.status, result.error) == ("host_failed", "login_profile_required")
    assert docker.commands == []


def test_login_enrollment_refuses_a_construct_without_a_login_plugin(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from silverquillm.karn import commands
    from silverquillm.karn.commands import enroll

    from .test_karn_host import make_candidate

    candidate = make_candidate(tmp_path)
    monkeypatch.setattr(commands, "load_candidate", lambda *args: candidate)
    result = CliRunner().invoke(
        enroll,
        [
            "--build-output",
            str(candidate.build_output),
            "--construct",
            "bare",
            "--state-root",
            str(tmp_path / "state"),
        ],
    )
    assert result.exit_code != 0
    assert "candidate_requires_login_plugin" in result.output


def test_the_native_telemetry_environment_is_allowlisted_and_recorded(tmp_path):
    from silverquillm.karn.definition import load_candidate
    from silverquillm.karn.host import DockerHost

    from .test_karn_host import FakeDocker, make_candidate

    candidate = make_candidate(tmp_path)
    candidate.runtime["environment"]["CLAUDE_CODE_ENABLE_TELEMETRY"] = "0"
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    candidate = load_candidate(
        candidate.build_output, "bare", image_inspector=lambda ref: {"Id": ref}
    )
    docker = FakeDocker()
    result = DockerHost(docker=docker).run(
        candidate,
        tmp_path / "ws",
        tmp_path / "run",
        "task",
        runtime_environment=lambda network: {"CLAUDE_CODE_ENABLE_TELEMETRY": "1"},
    )
    assert result.status == "completed"
    create = next(command for command in docker.commands if command[0] == "create")
    assert "CLAUDE_CODE_ENABLE_TELEMETRY=1" in create
    assert "CLAUDE_CODE_ENABLE_TELEMETRY=0" not in create
    assert result.host_configuration["environment"] == {"CLAUDE_CODE_ENABLE_TELEMETRY": "1"}
    refused = DockerHost(docker=FakeDocker()).run(
        make_candidate(tmp_path / "other"),
        tmp_path / "ws2",
        tmp_path / "run2",
        "task",
        runtime_environment=lambda network: {"LD_PRELOAD": "/tmp/x.so"},
    )
    assert refused.error == "undeclared_runtime_environment_override"
