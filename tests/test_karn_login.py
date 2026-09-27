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
    admit_plugin_mounts,
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
        delivered = admit_plugin_mounts(
            mounts, plugin.invoke("before_container_mount", "first", mounts), profile.state
        )
        native = Path(delivered[-1]["Source"])
        assert delivered[-1]["Target"] == "/native" and delivered[-1]["ReadOnly"] is False
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


def stalling_plugin(tmp_path, artifact):
    """A stand-in plugin process that answers the handshake, then replies to its first
    invocation only after the host has given up on it."""
    identity = {key: artifact.manifest[key] for key in ("id", "version", "sdk_major", "hooks")}
    script = tmp_path / "stalling-python"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, sys, time\n"
        f"identity = {identity!r}\n"
        "invocations = 0\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    result = {'ready': True}\n"
        "    if request['method'] == 'plugin.hello':\n"
        "        result = identity\n"
        "    elif request['method'] == 'plugin.invoke':\n"
        "        invocations += 1\n"
        "        if invocations == 1:\n"
        "            time.sleep(1)\n"
        "        result = []\n"
        "    print(json.dumps({'id': request['id'], 'result': result}), flush=True)\n"
    )
    script.chmod(0o755)
    return script


def test_a_timed_out_plugin_is_killed_so_its_late_reply_answers_nothing(
    tmp_path, artifact, monkeypatch
):
    profile = LoginProfile(tmp_path / "login", "research")
    with PluginProcess(artifact, stalling_plugin(tmp_path, artifact), profile) as plugin:
        with pytest.raises(KarnError, match="login_plugin_unavailable"):
            plugin.request("plugin.invoke", {}, timeout=0.2)
        assert plugin.process.poll() is not None
        signalled = []
        monkeypatch.setattr(os, "killpg", lambda *arguments: signalled.append(arguments))
        with pytest.raises(KarnError, match="login_plugin_unavailable"):
            plugin.request("plugin.invoke", {})
        assert signalled == []


def bind(source, target, read_only=False):
    return {"Type": "bind", "Source": str(source), "Target": target, "ReadOnly": read_only}


@pytest.fixture
def plugin_state(tmp_path):
    state = tmp_path / "login/plugin"
    (state / "work").mkdir(parents=True)
    return state


def test_admitted_plugin_mounts_extend_the_passed_list_from_the_plugin_state(
    tmp_path, plugin_state
):
    passed = [bind(tmp_path, "/output")]
    returned = [*passed, bind(plugin_state / "work/../work", "/native")]
    assert admit_plugin_mounts(passed, returned, plugin_state) == [
        *passed,
        bind((plugin_state / "work").resolve(), "/native"),
    ]
    assert admit_plugin_mounts(passed, list(passed), plugin_state) == passed


@pytest.mark.parametrize(
    "returned",
    [
        pytest.param(lambda passed, add: "not a list", id="not-a-list"),
        pytest.param(lambda passed, add: [add], id="passed-mount-dropped"),
        pytest.param(
            lambda passed, add: [{**passed[0], "ReadOnly": True}, add], id="passed-mount-changed"
        ),
        pytest.param(lambda passed, add: [add, *passed], id="passed-mount-reordered"),
        pytest.param(lambda passed, add: [*passed, *[add] * 33], id="too-many"),
    ],
)
def test_a_plugin_may_not_alter_the_mounts_it_was_passed(tmp_path, plugin_state, returned):
    passed = [bind(tmp_path, "/output")]
    reply = returned(passed, bind(plugin_state / "work", "/native"))
    with pytest.raises(KarnError, match="plugin_mount_refused:mount_list_altered"):
        admit_plugin_mounts(passed, reply, plugin_state)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"Type": "volume"}, "invalid_mount"),
        ({"ReadOnly": 0}, "invalid_mount"),
        ({"Extra": True}, "invalid_mount"),
        ({"Target": "/native,readonly=false"}, "invalid_mount"),
        ({"Target": "/home\n/native"}, "invalid_mount"),
        ({"Target": "/output\r"}, "invalid_mount"),
        ({"Target": '/na"tive'}, "invalid_mount"),
        ({"Target": "/"}, "target_conflict"),
        ({"Target": "native"}, "target_conflict"),
        ({"Target": "//output"}, "target_conflict"),
        ({"Target": "/native/"}, "target_conflict"),
        ({"Target": "/native/../output"}, "target_conflict"),
        ({"Target": "/output"}, "target_conflict"),
        ({"Target": "/output/nested"}, "target_conflict"),
        ({"Target": "/native/./x"}, "target_conflict"),
        ({"Source": "work"}, "source_outside_state_dir"),
    ],
)
def test_a_malformed_or_overlapping_plugin_mount_is_refused(tmp_path, plugin_state, change, reason):
    passed = [bind(tmp_path / "output", "/output")]
    added = {**bind(plugin_state / "work", "/native"), **change}
    with pytest.raises(KarnError, match="plugin_mount_refused:" + reason):
        admit_plugin_mounts(passed, [*passed, added], plugin_state)


def test_a_plugin_mount_may_only_expose_its_own_state(tmp_path, plugin_state):
    passed = [bind(tmp_path / "output", "/output")]
    outside = tmp_path / "home"
    outside.mkdir()
    (plugin_state / "escape").symlink_to(outside)
    (tmp_path / "login/plugin-sibling").mkdir()
    for source, reason in [
        (outside, "source_outside_state_dir"),
        (plugin_state / "escape", "source_outside_state_dir"),
        (plugin_state / "work/../../plugin-sibling", "source_outside_state_dir"),
        (plugin_state / "missing", "source_missing"),
    ]:
        with pytest.raises(KarnError, match="plugin_mount_refused:" + reason):
            admit_plugin_mounts(passed, [*passed, bind(source, "/native")], plugin_state)
    second = [*passed, bind(plugin_state / "work", "/native"), bind(plugin_state, "/native/x")]
    with pytest.raises(KarnError, match="plugin_mount_refused:target_conflict"):
        admit_plugin_mounts(passed, second, plugin_state)
