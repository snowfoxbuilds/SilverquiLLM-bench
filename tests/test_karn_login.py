from __future__ import annotations

import base64
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from silverquillm.karn.definition import KarnError, PluginArtifact, canonical, digest
from silverquillm.karn.login import (
    LoginProfile,
    PluginProcess,
    enroll_login,
    install_plugin,
    recover_login,
)

FIXTURE = Path(__file__).parent / "fixtures/karn/login-build/plugins/karn-codex-login-0.1.0"


def login_bytes(token="initial"):
    return canonical(
        {
            "auth_mode": "chatgpt",
            "tokens": {
                key: token + "-" + key
                for key in ("access_token", "refresh_token", "id_token", "account_id")
            },
        }
    )


def enrolled(profile):
    profile.set_secret(
        "login." + profile.name,
        canonical(
            {
                "format": 1,
                "revision": "a" * 32,
                "files": {"auth.json": base64.b64encode(login_bytes()).decode()},
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
        artifact, tmp_path_factory.mktemp("login-plugin-cache"), python=sys.executable
    )


def test_same_local_binding_excludes_direct_run_and_enrollment(tmp_path, artifact, monkeypatch):
    profile = LoginProfile(tmp_path / "login", "research")
    monkeypatch.setattr(
        "silverquillm.karn.login.install_plugin",
        lambda *a, **kw: pytest.fail("must lock before install"),
    )
    with profile.exclusive():
        with (
            pytest.raises(KarnError, match="login_in_use"),
            LoginProfile(profile.directory, "research").exclusive(),
        ):
            pass
        with pytest.raises(KarnError, match="login_in_use"):
            enroll_login(profile, artifact, tmp_path / "cache", lambda *args: None)
    with profile.exclusive():
        pass


def test_real_plugin_projects_fresh_state_and_persists_refresh(tmp_path, artifact, plugin_python):
    profile = LoginProfile(tmp_path / "login", "research")
    enrolled(profile)
    output = tmp_path / "output"
    output.mkdir()
    mounts = [{"Type": "bind", "Source": str(output), "Target": "/output", "ReadOnly": False}]
    with profile.exclusive(), PluginProcess(artifact, plugin_python, profile) as plugin:
        delivered = plugin.invoke("before_container_mount", "first", mounts)
        native = Path(delivered[-1]["Source"])
        assert {p.name for p in native.iterdir()} == {"auth.json"}
        assert stat.S_IMODE((native / "auth.json").stat().st_mode) == 0o600
        (native / "auth.json").write_bytes(login_bytes("refreshed"))
        (native / "session-history.jsonl").write_text("private history")
        (output / "result.json").write_text('{"failure_code":"authentication"}')
        plugin.invoke("after_container_exit", "first", delivered)
        assert not native.exists()
        assert plugin.status() == [{"login": "research", "codex-login": "relogin needed"}]
        second = plugin.invoke("before_container_mount", "second", mounts)
        native = Path(second[-1]["Source"])
        assert {p.name for p in native.iterdir()} == {"auth.json"}
        assert (native / "auth.json").read_bytes() == login_bytes("refreshed")
        plugin.invoke("after_container_exit", "second", second)
    assert stat.S_IMODE((profile.directory / "secret.json").stat().st_mode) == 0o600


def test_failed_persistence_keeps_auth_until_recovery_confirms_stop(
    tmp_path, artifact, plugin_python, monkeypatch
):
    profile = LoginProfile(tmp_path / "login", "research")
    enrolled(profile)
    with profile.exclusive(), PluginProcess(artifact, plugin_python, profile) as plugin:
        mounts = plugin.invoke("before_container_mount", "run", [])
        (profile.state / "work/auth.json").write_bytes(login_bytes("refreshed"))
        profile.journal(
            {
                "run_id": "run",
                "container_name": "orphan",
                "mounts": mounts,
                "plugin_artifact": artifact.row["artifact"],
            }
        )
        with monkeypatch.context() as patch:

            def unavailable(*args):
                raise KarnError("store_unavailable")

            patch.setattr(LoginProfile, "set_secret", unavailable)
            plugin.invoke("after_container_exit", "run", mounts)
        assert (profile.state / "work/auth.json").exists()
        assert profile.pending() is not None
        stopped = []

        def stop(name, run_id):
            assert (profile.state / "work/auth.json").exists()
            stopped.append((name, run_id))

        cleaned = []

        def cleanup(name, run_id):
            assert not (profile.state / "work").exists()
            assert profile.pending() is not None
            cleaned.append((name, run_id))

        recover_login(profile, plugin, stop, cleanup=cleanup)
        assert cleaned == [("orphan", "run")]
        assert stopped == [("orphan", "run")]
        assert not (profile.state / "work").exists()
        assert profile.pending() is None
        saved = json.loads(profile.get_secret("login.research"))
        assert base64.b64decode(saved["files"]["auth.json"]) == login_bytes("refreshed")


def test_failed_orphan_stop_never_harvests_live_auth(tmp_path, artifact, plugin_python):
    profile = LoginProfile(tmp_path / "login", "research")
    enrolled(profile)
    with profile.exclusive(), PluginProcess(artifact, plugin_python, profile) as plugin:
        mounts = plugin.invoke("before_container_mount", "run", [])
        profile.journal(
            {
                "run_id": "run",
                "container_name": "orphan",
                "mounts": mounts,
                "plugin_artifact": artifact.row["artifact"],
            }
        )

        def unconfirmed(*args):
            raise KarnError("container_stop_unconfirmed")

        with pytest.raises(KarnError, match="container_stop_unconfirmed"):
            recover_login(profile, plugin, unconfirmed)
        assert profile.pending() is not None
        assert (profile.state / "work/auth.json").exists()


def test_setup_uses_same_plugin_with_isolated_native_home(
    tmp_path, artifact, plugin_python, monkeypatch
):
    profile = LoginProfile(tmp_path / "login", "research")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cli = fake_bin / "codex"
    cli.write_text(
        "#!/usr/bin/env python3\nimport os, pathlib\n"
        "assert 'OPENAI_API_KEY' not in os.environ\n"
        "p=pathlib.Path(os.environ['CODEX_HOME'])\n"
        "assert not list(p.iterdir())\n"
        f"(p/'auth.json').write_bytes({login_bytes('enrolled')!r})\n"
    )
    cli.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-login")
    with profile.exclusive(), PluginProcess(artifact, plugin_python, profile) as plugin:
        assert plugin.setup() == 0
    saved = json.loads(profile.get_secret("login.research"))
    assert base64.b64decode(saved["files"]["auth.json"]) == login_bytes("enrolled")
    assert not list(profile.state.glob("setup-*"))
