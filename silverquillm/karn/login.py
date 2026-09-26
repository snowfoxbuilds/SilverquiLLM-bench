"""Host the unchanged Karn login plugin under one local, whole-run login lock."""

from __future__ import annotations

import base64
import binascii
import contextlib
import fcntl
import hmac
import os
import queue
import secrets
import shutil
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .definition import KarnError, PluginArtifact, canonical, read_regular, strict_json

MAX_MESSAGE = 1024 * 1024
NATIVE_PRESERVED = "native-preserved"
MAX_NATIVE_BYTES = 128 * 1024 * 1024


class LoginInUseError(KarnError):
    """Another local runner holds this login; the caller may retry later."""


def private_directory(path: Path) -> Path:
    path = Path(path).absolute()
    if path.resolve() != path:
        raise KarnError("unsafe_login_directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise KarnError("login_directory_must_be_private")
    return path


def write_private(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


@dataclass(frozen=True)
class LoginProfile:
    directory: Path
    name: str

    def __post_init__(self):
        if not self.name or self.name in (".", "..") or any(c in self.name for c in "/\\\0"):
            raise KarnError("invalid_login_profile")
        object.__setattr__(self, "directory", private_directory(Path(self.directory)))

    @property
    def state(self) -> Path:
        return private_directory(self.directory / "plugin")

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[None]:
        descriptor = os.open(
            self.directory / "runner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LoginInUseError("login_in_use") from None
            yield
        finally:
            os.close(descriptor)

    def get_secret(self, name: str) -> str:
        if name != "login." + self.name:
            raise KarnError("secret_unavailable")
        path = self.directory / "secret.json"
        try:
            value = strict_json(read_regular(path, limit=2 * 65536 + 2))
        except KarnError:
            raise KarnError("secret_unavailable") from None
        if not isinstance(value, str):
            raise KarnError("secret_unavailable")
        return value

    def set_secret(self, name: str, value: str) -> None:
        if (
            name != "login." + self.name
            or not isinstance(value, str)
            or len(value.encode()) > 65536
        ):
            raise KarnError("invalid_secret")
        write_private(self.directory / "secret.json", canonical(value))

    def pending(self) -> dict | None:
        path = self.directory / "active.json"
        if not path.exists():
            return None
        value = strict_json(read_regular(path))
        if not isinstance(value, dict):
            raise KarnError("invalid_login_recovery_journal")
        return value

    def journal(self, value: dict) -> None:
        write_private(self.directory / "active.json", canonical(value))

    def settled(self) -> None:
        (self.directory / "active.json").unlink(missing_ok=True)


def install_plugin(artifact: PluginArtifact, cache: Path, *, python: str | None = None) -> Path:
    """Install the already built, pinned wheel closure offline; never build a wheel."""
    artifact.verify()
    expected = artifact.manifest["python"]
    selected = python or (
        sys.executable
        if expected == f"{sys.version_info.major}.{sys.version_info.minor}"
        else shutil.which("python" + expected)
    )
    if not selected:
        raise KarnError("plugin_python_unavailable:" + expected)
    version = subprocess.run(
        [selected, "-I", "-c", "import sys; print('%s.%s' % sys.version_info[:2])"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if version.returncode or version.stdout.strip() != expected:
        raise KarnError("plugin_python_mismatch")
    cache = private_directory(Path(cache))
    target = cache / artifact.row["artifact"].split(":", 1)[1]
    lock = os.open(cache / (target.name + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stamp = target / "artifact.json"
        if stamp.exists() and read_regular(stamp) == canonical(artifact.manifest):
            executable = target / "bin/python"
            if executable.is_file():
                return executable
        if target.exists():
            raise KarnError("incomplete_plugin_environment")
        temporary = Path(tempfile.mkdtemp(prefix=".install-", dir=cache))
        try:
            environment = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "PIP_CONFIG_FILE": "/dev/null",
            }
            commands = [
                [selected, "-I", "-m", "venv", str(temporary)],
                [
                    str(temporary / "bin/python"),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    "--disable-pip-version-check",
                    *[str(path) for path, _ in artifact.wheels],
                ],
            ]
            for command in commands:
                result = subprocess.run(
                    command, capture_output=True, env=environment, check=False, timeout=180
                )
                if result.returncode:
                    raise KarnError("plugin_offline_install_failed")
            write_private(temporary / "artifact.json", canonical(artifact.manifest))
            os.rename(temporary, target)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return target / "bin/python"
    finally:
        os.close(lock)


def secret_values(opaque: str) -> set[bytes]:
    """Register opaque secret documents and their encoded leaves for diagnostic redaction."""
    found = set()

    def visit(value, depth=0):
        if depth > 8:
            return
        if isinstance(value, dict):
            for child in value.values():
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
        elif isinstance(value, str) and 8 <= len(value.encode()) <= 65536:
            encoded = value.encode()
            if encoded in found:
                return
            found.add(encoded)
            try:
                visit(strict_json(encoded), depth + 1)
            except KarnError:
                pass
            try:
                decoded = base64.b64decode(encoded, validate=True)
                visit(decoded.decode(), depth + 1)
            except (ValueError, UnicodeError, binascii.Error):
                pass

    visit(opaque)
    return found


class _CallbackServer(socketserver.UnixStreamServer):
    def __init__(self, path: str, profile: LoginProfile, token: str):
        self.profile, self.token = profile, token
        self.redactions = set()
        super().__init__(path, _Callback)


class _Callback(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(30)
        try:
            raw = self.rfile.readline(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE:
                raise KarnError("message_too_large")
            request = strict_json(raw)
            if (
                not isinstance(request, dict)
                or not isinstance(request.get("token"), str)
                or not hmac.compare_digest(request["token"], self.server.token)
            ):
                raise KarnError("invalid_capability")
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise KarnError("invalid_params")
            method = request.get("method")
            if method == "get_secret":
                value = self.server.profile.get_secret(params.get("name"))
                self.server.redactions.update(secret_values(value))
                result = {"value": value}
            elif method == "set_secret":
                if isinstance(params.get("value"), str):
                    self.server.redactions.update(secret_values(params["value"]))
                self.server.profile.set_secret(params.get("name"), params.get("value"))
                result = {"stored": True}
            else:
                raise KarnError("capability_unavailable")
            reply = {"result": result}
        except (KarnError, OSError, ValueError, TypeError):
            reply = {"error": "secret_unavailable"}
        self.wfile.write(canonical(reply) + b"\n")


class PluginProcess:
    def __init__(self, artifact: PluginArtifact, python: Path, profile: LoginProfile):
        self.artifact, self.python, self.profile = artifact, Path(python), profile
        self.process = None
        self.server = None
        self.socket_directory = None
        self.replies = queue.Queue()

    def __enter__(self):
        self.socket_directory = Path(tempfile.mkdtemp(prefix="sq-login-"))
        token = secrets.token_hex(32)
        self.server = _CallbackServer(
            str(self.socket_directory / "callback.sock"), self.profile, token
        )
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.environment = {
            key: os.environ[key] for key in ("PATH", "TERM", "LANG") if key in os.environ
        }
        self.environment.update(
            HOME=str(self.profile.state),
            THEOZOLITH_STACK=self.profile.name,
            THEOZOLITH_CALLBACK_SOCKET=str(self.socket_directory / "callback.sock"),
            THEOZOLITH_CALLBACK_TOKEN=token,
            THEOZOLITH_PLUGIN_ID=self.artifact.row["id"],
        )
        try:
            self.process = subprocess.Popen(
                [str(self.python), "-I", "-m", self.artifact.manifest["module"]],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=self.environment,
                cwd=self.profile.state,
                start_new_session=True,
            )
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            hello = self.request("plugin.hello", {})
            for key in ("id", "version", "sdk_major", "hooks"):
                if hello.get(key) != self.artifact.manifest[key]:
                    raise KarnError("plugin_process_identity_mismatch")
            self.request(
                "plugin.activate", {"configuration": self.artifact.row.get("configuration", {})}
            )
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _read(self):
        while True:
            line = self.process.stdout.readline(MAX_MESSAGE + 1)
            self.replies.put(line)
            if not line or len(line) > MAX_MESSAGE:
                return

    def request(self, method: str, params: dict, *, timeout: float = 60):
        request_id = secrets.token_hex(8)
        try:
            self.process.stdin.write(
                canonical({"id": request_id, "method": method, "params": params}) + b"\n"
            )
            self.process.stdin.flush()
            raw = self.replies.get(timeout=timeout)
        except (OSError, queue.Empty):
            raise KarnError("login_plugin_unavailable") from None
        if not raw or len(raw) > MAX_MESSAGE:
            raise KarnError("login_plugin_invalid_reply")
        reply = strict_json(raw)
        if not isinstance(reply, dict) or reply.get("id") != request_id:
            raise KarnError("login_plugin_invalid_reply")
        if "error" in reply:
            code = reply["error"]
            if not isinstance(code, str) or not code.replace("_", "").isalnum():
                code = "hook_failed"
            raise KarnError("login_plugin:" + code)
        return reply.get("result")

    def invoke(self, hook: str, run_id: str, mounts: list[dict]):
        return self.request(
            "plugin.invoke",
            {
                "hook": hook,
                "context": {
                    "stack": self.profile.name,
                    "run_id": run_id,
                    "configuration": self.artifact.row.get("configuration", {}),
                },
                "payload": {"mounts": mounts},
            },
        )

    @property
    def redactions(self) -> set[bytes]:
        return set(self.server.redactions)

    def setup(self) -> int:
        result = subprocess.run(
            [str(self.python), "-I", "-m", self.artifact.manifest["module"], "--setup"],
            env=self.environment,
            cwd=self.profile.state,
            check=False,
        )
        return result.returncode

    def status(self) -> list[dict]:
        return self.request(
            "plugin.invoke",
            {
                "hook": "on_render_status",
                "context": {"stack": self.profile.name, "configuration": {}},
                "payload": {"rows": [{"login": self.profile.name}]},
            },
        )

    def __exit__(self, *_):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process.stdin.close()
            self.process.stdout.close()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server_thread.join(timeout=5)
        if self.socket_directory is not None:
            shutil.rmtree(self.socket_directory)


def _mounted_run(profile: LoginProfile) -> str | None:
    try:
        value = strict_json(read_regular(profile.state / "mounted.json", limit=4096))
    except KarnError:
        return None
    return value.get("run_id") if isinstance(value, dict) else None


def preserve_pending_native(profile: LoginProfile) -> dict | None:
    """Copy a pending run's native session journals, never auth, into that run's own evidence.

    Called under profile.exclusive before recover_login settles the pending run, because
    settling clears the plugin's work directory. State is attributed to the pending run only
    when the journal and the plugin's mounted.json name the same run.
    """
    pending = profile.pending()
    if pending is None:
        return None
    run_id = pending.get("run_id")
    outcome = {"run_id": run_id, "preserved": False, "reason": None}
    sessions = profile.state / "work" / "sessions"
    evidence = pending.get("evidence_dir")
    if _mounted_run(profile) != run_id or sessions.is_symlink() or not sessions.is_dir():
        outcome["reason"] = "native_state_unavailable"
        return outcome
    if not isinstance(evidence, str) or not Path(evidence).is_dir():
        outcome["reason"] = "native_state_run_directory_unavailable"
        return outcome
    target = Path(evidence) / NATIVE_PRESERVED
    if target.exists():
        outcome["preserved"] = True
        return outcome
    temporary = Path(tempfile.mkdtemp(prefix=".native-", dir=evidence))
    try:
        consumed = 0
        for directory, names, files in os.walk(sessions, followlinks=False):
            names[:] = [name for name in names if not (Path(directory) / name).is_symlink()]
            for name in sorted(files):
                if not name.startswith("rollout-") or not name.endswith(".jsonl"):
                    continue
                source = Path(directory) / name
                content = read_regular(source, limit=MAX_NATIVE_BYTES - consumed)
                consumed += len(content)
                destination = temporary / "sessions" / source.relative_to(sessions)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
        os.rename(temporary, target)
        outcome["preserved"] = True
    except (KarnError, OSError):
        outcome["reason"] = "native_state_copy_failed"
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return outcome


def recover_login(
    profile: LoginProfile,
    plugin: PluginProcess,
    stop_and_confirm: Callable[[str, str], None],
    *,
    cleanup: Callable[[str, str], None] | None = None,
) -> None:
    """Called under profile.exclusive; leave the journal intact until stop and harvest finish."""
    pending = profile.pending()
    if pending is None:
        return
    if pending.get("plugin_artifact") != plugin.artifact.row["artifact"]:
        raise KarnError("login_recovery_requires_previous_plugin")
    stop_and_confirm(pending["container_name"], pending["run_id"])
    plugin.invoke("after_container_exit", pending["run_id"], pending["mounts"])
    if (profile.state / "mounted.json").exists():
        raise KarnError("login_harvest_pending")
    if cleanup is not None:
        cleanup(pending["container_name"], pending["run_id"])
    profile.settled()


def enroll_login(
    profile: LoginProfile,
    artifact: PluginArtifact,
    cache: Path,
    stop_and_confirm: Callable[[str, str], None],
    *,
    python: str | None = None,
    cleanup: Callable[[str, str], None] | None = None,
) -> int:
    with profile.exclusive():
        executable = install_plugin(artifact, cache, python=python)
        with PluginProcess(artifact, executable, profile) as plugin:
            recover_login(profile, plugin, stop_and_confirm, cleanup=cleanup)
            return plugin.setup()
