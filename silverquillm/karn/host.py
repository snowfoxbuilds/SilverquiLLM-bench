"""Execute declared Karn workloads independently and retain stopped partial work."""

from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .definition import (
    KarnCandidate,
    KarnError,
    canonical,
    digest,
    inside,
    read_regular,
    strict_json,
)
from .docker import RUN_LABEL, Docker, Network
from .login import (
    LoginProfile,
    PluginProcess,
    enroll_login,
    install_plugin,
    preserve_pending_native,
    recover_login,
)

DEFAULT_BUDGET_SECONDS = 24 * 60 * 60
# The standard-library modules proxy.py imports inside the candidate image.
PROXY_PROBE = "import ipaddress, json, os, select, socket, socketserver, urllib.request"


def validate_budget(candidate: KarnCandidate, budget_seconds: int) -> None:
    if type(budget_seconds) is not int or budget_seconds < 1:
        raise KarnError("invalid_execution_budget")
    ceiling = candidate.runtime["timeout_seconds"]
    if ceiling is not None and ceiling < budget_seconds:
        raise KarnError("definition_timeout_shorter_than_budget")


@dataclass
class HostResult:
    run_id: str
    identity: dict
    container_name: str
    workspace_path: str
    evidence_dir: str
    budget_seconds: int
    status: str = "host_failed"
    failure_stage: str | None = None
    error: str | None = None
    exit_code: int | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    output_path: str | None = None
    result_document: object | None = None
    workspace_stopped: bool = False
    login_state: list[dict] = field(default_factory=list)
    observation_errors: list[str] = field(default_factory=list)
    log_paths: dict[str, str] = field(default_factory=dict)
    host_configuration: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _mount(source: Path, target: str, readonly: bool) -> dict:
    return {"Type": "bind", "Source": str(source.resolve()), "Target": target, "ReadOnly": readonly}


def _host_file(mounts: list[dict], guest: str) -> Path:
    matches = [m for m in mounts if PurePosixPath(guest).is_relative_to(m["Target"])]
    if not matches:
        raise KarnError("unbound_guest_file")
    selected = max(matches, key=lambda m: len(PurePosixPath(m["Target"]).parts))
    relative = PurePosixPath(guest).relative_to(selected["Target"])
    return (
        Path(selected["Source"])
        if not relative.parts
        else inside(Path(selected["Source"]), str(relative))
    )


class DockerHost:
    def __init__(
        self,
        *,
        docker: Docker | None = None,
        plugin_cache: Path | None = None,
        plugin_python: str | None = None,
        poll_interval: float = 0.2,
    ):
        self.docker = docker or Docker()
        self.plugin_cache = plugin_cache or Path.home() / ".local/state/silverquillm/karn/plugins"
        self.plugin_python = plugin_python
        self.poll_interval = poll_interval

    def preflight(self, candidate: KarnCandidate, budget_seconds: int) -> None:
        """Refuse before any run directory exists when the host cannot honor the definition."""
        validate_budget(candidate, budget_seconds)
        if candidate.runtime["network"]["mode"] != "restricted":
            return
        # The egress proxy sidecar runs the candidate image's own python3 (see docker.Network).
        probe = self.docker.command(
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--entrypoint",
            "python3",
            candidate.image_id,
            "-I",
            "-c",
            PROXY_PROBE,
            timeout=60,
            check=False,
        )
        if probe.returncode:
            raise KarnError("restricted_network_requires_python3")

    def enroll_login(self, profile: LoginProfile, artifact) -> int:
        return enroll_login(
            profile,
            artifact,
            self.plugin_cache,
            self.docker.stop_and_confirm,
            python=self.plugin_python,
            cleanup=self.docker.cleanup_run,
        )

    def _stage(self, candidate, workspace, evidence, prompt, file_inputs, mount_bindings):
        mounts, named = [], {}
        for row in candidate.runtime["mounts"]:
            if row["name"] in mount_bindings:
                source = Path(mount_bindings[row["name"]]).resolve()
                if not source.exists():
                    raise KarnError("mount_binding_missing:" + row["name"])
            elif row["source"]["kind"] == "runtime" and not row["persistent"]:
                source = (
                    workspace
                    if row["purpose"] == "workspace"
                    else evidence / "mounts" / row["name"]
                )
                source.mkdir(mode=0o700, parents=True, exist_ok=(source == workspace))
            else:
                raise KarnError("mount_binding_required:" + row["name"])
            named[row["name"]] = source
            if row.get("exposure", "container") == "container":
                mounts.append(_mount(source, row["target"], row["access"] == "read_only"))
        inputs = dict(file_inputs)
        if prompt is not None:
            inputs["prompt"] = prompt.encode()
        declared = {row["name"]: row for row in candidate.runtime["files"]}
        for name, content in inputs.items():
            row = declared.get(name)
            if row is None or row["direction"] != "input":
                raise KarnError("input_surface_missing:" + name)
            path = inside(named[row["mount"]], row["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise KarnError("input_already_exists:" + name)
            path.write_bytes(content.encode() if isinstance(content, str) else content)
        return mounts, named

    def _bootstrap(self, candidate, run_id, mounts):
        runtime = candidate.runtime
        command = list(runtime["main"])
        if runtime["initializer"] is not None:
            command = [
                *runtime["initializer_runner"],
                "--initializer-json",
                json.dumps(runtime["initializer"]),
                "--",
                *command,
            ]
        bootstrap = runtime["bootstrap"]
        if bootstrap is None:
            return command, f"{os.getuid()}:{os.getgid()}", None
        if os.getuid() == 0 or os.getgid() == 0:
            raise KarnError("bootstrap_requires_nonroot_host_identity")
        identity = {
            "version": 1,
            "launch_id": run_id,
            "uid": os.getuid(),
            "gid": os.getgid(),
            "sudo": runtime["sudo"],
            "home": bootstrap["home"],
            "shell": bootstrap["shell"],
        }
        source = _host_file(mounts, bootstrap["identity_input"])
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(canonical(identity))
        handoff = _host_file(mounts, bootstrap["handoff"])
        handoff.parent.mkdir(parents=True, exist_ok=True)
        handoff.write_bytes(b"")
        handoff.chmod(0o600)
        mounts.extend(
            [
                _mount(source, bootstrap["identity_input"], True),
                _mount(handoff, bootstrap["handoff"], False),
            ]
        )
        command = [
            *bootstrap["argv"],
            "--identity-input",
            bootstrap["identity_input"],
            "--handoff",
            bootstrap["handoff"],
            "--protocol",
            bootstrap["protocol"],
            "--",
            *command,
        ]
        return command, "0:0", handoff

    def _create(self, candidate, name, run_id, command, user, mounts, network, environment):
        arguments = [
            "create",
            "--pull",
            "never",
            "--name",
            name,
            "--label",
            RUN_LABEL + "=" + run_id,
            "--user",
            user,
            "--network",
            network.network,
        ]
        if network.policy["mode"] == "restricted":
            arguments += ["--dns", "127.0.0.1"]
        if not candidate.runtime["sudo"]:
            arguments += ["--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
            if candidate.runtime["bootstrap"]:
                for capability in ("CHOWN", "DAC_OVERRIDE", "FOWNER", "SETUID", "SETGID"):
                    arguments += ["--cap-add", capability]
        for key, value in environment.items():
            arguments += ["--env", key + "=" + value]
        seen = set()
        for mount in mounts:
            if (
                mount.get("Type") != "bind"
                or not isinstance(mount.get("Source"), str)
                or not Path(mount["Source"]).is_absolute()
                or not isinstance(mount.get("Target"), str)
                or not mount["Target"].startswith("/")
                or mount["Target"] in seen
                or any("," in mount[key] or "\0" in mount[key] for key in ("Source", "Target"))
            ):
                raise KarnError("invalid_container_mount")
            seen.add(mount["Target"])
            specification = f"type=bind,src={mount['Source']},dst={mount['Target']}"
            if mount.get("ReadOnly"):
                specification += ",readonly"
            arguments += ["--mount", specification]
        resources = candidate.runtime["resources"]
        for key, option in (
            ("cpus", "--cpus"),
            ("memory_bytes", "--memory"),
            ("pids", "--pids-limit"),
        ):
            if resources[key] is not None:
                arguments += [option, str(resources[key])]
        arguments += ["--entrypoint", command[0], candidate.image_id, *command[1:]]
        self.docker.command(*arguments)

    def run(
        self,
        candidate: KarnCandidate,
        workspace: Path,
        evidence_dir: Path,
        prompt: str | None,
        *,
        budget_seconds: int = DEFAULT_BUDGET_SECONDS,
        login_profile: LoginProfile | None = None,
        run_id: str | None = None,
        file_inputs: dict | None = None,
        mount_bindings: dict | None = None,
        extra_environment: dict | None = None,
        extra_mounts: list[dict] | None = None,
        runtime_config: str | Callable[[Network], str] | None = None,
        after_stop: Callable[[HostResult, Path | None], None] | None = None,
        collector_endpoint: str | None = None,
        login_lock_held: bool = False,
    ) -> HostResult:
        validate_budget(candidate, budget_seconds)
        candidate.verify(self.docker.inspect_image)
        run_id = run_id or uuid.uuid4().hex
        if not run_id or len(run_id) > 64 or not all(c.isalnum() or c in "_.-" for c in run_id):
            raise KarnError("invalid_run_id")
        workspace, evidence = Path(workspace).resolve(), Path(evidence_dir).resolve()
        evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        if login_profile is not None and (
            login_profile.directory.is_relative_to(evidence)
            or login_profile.directory.is_relative_to(workspace)
            or evidence.is_relative_to(login_profile.directory)
            or workspace.is_relative_to(login_profile.directory)
        ):
            raise KarnError("authentication_must_be_outside_evidence")
        allowed_environment = {
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
            "OTEL_EXPORTER_OTLP_PROTOCOL",
            "OTEL_SERVICE_NAME",
        }
        if set(extra_environment or {}) - allowed_environment:
            raise KarnError("undeclared_runtime_environment_override")
        infrastructure_mounts = []
        for mount in extra_mounts or []:
            target = mount.get("Target", "")
            if not mount.get("ReadOnly") or not target.startswith("/run/silverquillm/"):
                raise KarnError("infrastructure_mount_must_be_readonly_and_scoped")
            if any(
                PurePosixPath(target).is_relative_to(row["target"])
                or PurePosixPath(row["target"]).is_relative_to(target)
                for row in candidate.runtime["mounts"]
                if row.get("exposure", "container") == "container"
            ):
                raise KarnError("infrastructure_mount_shadows_definition")
            source = Path(mount["Source"]).resolve()
            paths = sorted(source.rglob("*")) if source.is_dir() else [source]
            content = []
            for path in paths:
                if path.is_dir():
                    continue
                content.append(
                    [
                        str(path.relative_to(source)) if path != source else source.name,
                        digest(read_regular(path, limit=256 * 1024 * 1024)),
                    ]
                )
            infrastructure_mounts.append(
                {"target": target, "read_only": True, "digest": digest(canonical(content))}
            )
        result = HostResult(
            run_id,
            candidate.identity(),
            "sq-run-" + run_id,
            str(workspace),
            str(evidence),
            budget_seconds,
        )
        result.host_configuration = {
            "environment": extra_environment or {},
            "mounts": infrastructure_mounts,
        }
        stage = "preparation"
        plugin = None
        mounts = []
        named = {}
        native = None
        handoff = None
        lock = (
            login_profile.exclusive()
            if login_profile and not login_lock_held
            else contextlib.nullcontext()
        )
        try:
            with lock, contextlib.ExitStack() as lifecycle:
                if candidate.runtime["backend"] != "docker":
                    raise KarnError("runtime_backend_unavailable")
                if candidate.definition["mode"] != "automaton":
                    raise KarnError("automaton_required")
                if candidate.plugins:
                    for artifact in candidate.plugins:
                        if artifact.row["id"] != "karn-codex-login":
                            raise KarnError("runtime_plugin_unavailable:" + artifact.row["id"])
                    if login_profile is None:
                        raise KarnError("login_profile_required")
                    stage = "authentication"
                    artifact = candidate.plugins[0]
                    executable = install_plugin(
                        artifact, self.plugin_cache, python=self.plugin_python
                    )
                    plugin = lifecycle.enter_context(
                        PluginProcess(artifact, executable, login_profile)
                    )
                    stale = preserve_pending_native(login_profile)
                    if stale is not None and stale["reason"] not in (
                        None,
                        "native_state_unavailable",
                    ):
                        result.observation_errors.append(
                            f"stale_login_native_state_lost:{stale['run_id']}:{stale['reason']}"
                        )
                    recover_login(
                        login_profile,
                        plugin,
                        self.docker.stop_and_confirm,
                        cleanup=self.docker.cleanup_run,
                    )
                elif login_profile is not None:
                    raise KarnError("candidate_has_no_login_plugin")
                stage = "staging"
                network = None
                try:
                    mounts, named = self._stage(
                        candidate,
                        workspace,
                        evidence,
                        prompt,
                        file_inputs or {},
                        mount_bindings or {},
                    )
                    for row in candidate.runtime["mounts"]:
                        if row["purpose"] == "output":
                            result.output_path = str(named[row["name"]])
                    if any(
                        row.get("delivery") is not None for row in candidate.runtime["credentials"]
                    ):
                        raise KarnError("credential_delivery_unavailable")
                    command, user, handoff = self._bootstrap(candidate, run_id, mounts)
                    if plugin:
                        login_profile.journal(
                            {
                                "run_id": run_id,
                                "container_name": result.container_name,
                                "evidence_dir": str(evidence),
                                "plugin_artifact": artifact.row["artifact"],
                                "mounts": mounts,
                            }
                        )
                        mounts = plugin.invoke("before_container_mount", run_id, mounts)
                        if not isinstance(mounts, list):
                            raise KarnError("invalid_plugin_mount_reply")
                        login_profile.journal(
                            {
                                "run_id": run_id,
                                "container_name": result.container_name,
                                "evidence_dir": str(evidence),
                                "plugin_artifact": artifact.row["artifact"],
                                "mounts": mounts,
                            }
                        )
                        native = login_profile.state / "work"
                    stage = "network"
                    network = Network(
                        self.docker,
                        run_id,
                        candidate.runtime["network"],
                        candidate.image_id,
                        evidence,
                        collector_endpoint=collector_endpoint,
                    )
                    network.__enter__()
                    environment = {
                        **candidate.runtime["environment"],
                        **(extra_environment or {}),
                        **network.environment,
                    }
                    mounts.extend(extra_mounts or [])
                    if runtime_config is not None:
                        config = evidence / "native-observability.toml"
                        config.write_text(
                            runtime_config(network) if callable(runtime_config) else runtime_config
                        )
                        result.host_configuration["native_config_digest"] = digest(
                            config.read_bytes()
                        )
                        native_target = environment.get("CODEX_HOME")
                        if not native_target:
                            raise KarnError("native_home_required_for_observability")
                        mounts.append(_mount(config, native_target + "/config.toml", True))
                    stage = "launch"
                    self._create(
                        candidate,
                        result.container_name,
                        run_id,
                        command,
                        user,
                        mounts,
                        network,
                        environment,
                    )
                    started = time.monotonic()
                    self.docker.command("start", result.container_name)
                    result.started_at = _now()
                    stage = "execution"
                    while True:
                        info = self.docker.inspect_container(result.container_name)
                        if info is None:
                            raise KarnError("container_disappeared")
                        if not info["State"].get("Running"):
                            result.exit_code = info["State"].get("ExitCode")
                            result.status = "completed" if result.exit_code == 0 else "failed"
                            result.started_at = info["State"].get("StartedAt") or result.started_at
                            result.stopped_at = info["State"].get("FinishedAt") or _now()
                            break
                        if time.monotonic() - started >= budget_seconds:
                            result.status = "deadline"
                            break
                        time.sleep(self.poll_interval)
                except KeyboardInterrupt:
                    result.status = "interrupted"
                except (KarnError, OSError) as error:
                    result.failure_stage = stage
                    result.error = str(error) if isinstance(error, KarnError) else "host_os_error"
                finally:
                    try:
                        self._finish(
                            candidate,
                            result,
                            mounts,
                            named,
                            plugin,
                            login_profile,
                            native,
                            handoff,
                            after_stop,
                        )
                    finally:
                        if network is not None:
                            network.__exit__(None, None, None)
        except KeyboardInterrupt:
            result.status = "interrupted"
            result.failure_stage = stage
        except (KarnError, OSError) as error:
            result.status = "host_failed"
            result.failure_stage = stage
            result.error = str(error) if isinstance(error, KarnError) else "host_os_error"
        (evidence / "host-result.json").write_bytes(canonical(result.to_dict()) + b"\n")
        return result

    def _finish(
        self, candidate, result, mounts, named, plugin, profile, native, handoff, after_stop
    ):
        self.docker.stop_and_confirm(result.container_name, result.run_id)
        info = self.docker.inspect_container(result.container_name)
        if info is not None:
            result.exit_code = info["State"].get("ExitCode")
        result.workspace_stopped = True
        result.stopped_at = result.stopped_at or _now()
        if handoff is not None:
            try:
                value = strict_json(read_regular(handoff))
                version = 2 if candidate.runtime["bootstrap"]["protocol"] == "identity-v2" else 1
                if value != {
                    "version": version,
                    "launch_id": result.run_id,
                    "uid": os.getuid(),
                    "gid": os.getgid(),
                }:
                    raise KarnError("invalid_bootstrap_handoff")
            except KarnError:
                result.observation_errors.append("bootstrap_handoff_unconfirmed")
                if result.status == "completed":
                    result.status, result.failure_stage, result.error = (
                        "host_failed",
                        "bootstrap",
                        "bootstrap_handoff_unconfirmed",
                    )
        try:
            for row in candidate.runtime["files"]:
                if row["name"] == "result" and row["mount"] in named:
                    path = inside(named[row["mount"]], row["path"])
                    if path.exists():
                        document = strict_json(read_regular(path))

                        def no_remote_schema(uri):
                            raise NoSuchResource(ref=uri)

                        validator = Draft202012Validator(
                            row["schema"], registry=Registry(retrieve=no_remote_schema)
                        )
                        try:
                            valid = validator.is_valid(document)
                        except Exception:  # noqa: BLE001 -- malformed guest schemas remain an observation error.
                            valid = False
                        if valid:
                            result.result_document = document
                        else:
                            result.observation_errors.append("result_schema_mismatch")
        except KarnError:
            result.observation_errors.append("result_file_unreadable")
        if after_stop is not None:
            try:
                after_stop(result, native)
            except Exception:  # noqa: BLE001 -- observation failures must not skip authentication harvest.
                result.observation_errors.append("after_stop_observation_failed")
        if plugin:
            try:
                plugin.invoke("after_container_exit", result.run_id, mounts)
                result.login_state = plugin.status()
                if (profile.state / "mounted.json").exists():
                    result.observation_errors.append("login_harvest_pending")
                else:
                    profile.settled()
            except KarnError:
                result.observation_errors.append("login_harvest_failed")
        if plugin and result.result_document is not None:

            def sanitized(value):
                if isinstance(value, dict):
                    return {key: sanitized(child) for key, child in value.items()}
                if isinstance(value, list):
                    return [sanitized(child) for child in value]
                if isinstance(value, str):
                    data = value.encode()
                    for secret in sorted(plugin.redactions, key=len, reverse=True):
                        data = data.replace(secret, b"[REDACTED]")
                    return data.decode()
                return value

            result.result_document = sanitized(result.result_document)
        try:
            output = Path(result.evidence_dir)
            self.docker.logs(
                result.container_name,
                output / "stdout.log",
                output / "stderr.log",
                candidate.runtime["logs"],
                redactions=plugin.redactions if plugin else (),
            )
            result.log_paths = {
                "stdout": str(output / "stdout.log"),
                "stderr": str(output / "stderr.log"),
            }
        except KarnError:
            result.observation_errors.append("container_logs_unavailable")
        self.docker.remove(result.container_name)
