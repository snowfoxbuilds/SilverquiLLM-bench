"""Independent Docker host for the benchmark's declared-file Construct interface."""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from jsonschema import Draft202012Validator
from referencing import Registry

from silverquillm.safe_files import atomic_write, read_regular

OWNER_LABEL = "silverquillm.construct.owner"
ROLE_LABEL = "silverquillm.construct.role"
MAX_LOG_BYTES = 64 * 1024 * 1024


def validate_payload(schema, payload):
    Draft202012Validator(schema, registry=Registry()).validate(payload)


def container_name(run_id):
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id) is None:
        raise HostError("invalid run identifier")
    return "silverquillm-" + run_id


class HostError(RuntimeError):
    pass


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=30):
        super().__init__("localhost", timeout=timeout)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class DockerEngine:
    def __init__(self, socket_path=None):
        selected = socket_path or os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
        selected = selected.removeprefix("unix://")
        if not selected.startswith("/") or "\0" in selected:
            raise HostError("only an explicit local Docker Unix socket is supported")
        self.socket_path = selected

    def request(self, method, path, body=None, *, missing=False, raw=False, maximum=1048576):
        connection = UnixConnection(self.socket_path)
        try:
            connection.request(
                method,
                path,
                body=None if body is None else json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            data = response.read(maximum + 1)
            if missing and response.status == 404:
                return None
            if response.status == 304:
                return None
            if not 200 <= response.status < 300 or len(data) > maximum:
                raise HostError(
                    f"Docker {method} operation failed (HTTP {response.status}) or exceeded its response limit"
                )
            return data if raw else json.loads(data) if data else None
        except (OSError, ValueError, http.client.HTTPException):
            raise HostError("Docker observation or operation is unavailable") from None
        finally:
            connection.close()

    def inspect(self, identifier):
        return self.request(
            "GET", "/containers/" + quote(identifier, safe="") + "/json", missing=True
        )

    def image(self, reference):
        value = self.request("GET", "/images/" + quote(reference, safe="") + "/json", missing=True)
        if value is None:
            raise HostError("selected immutable image is unavailable locally")
        return value

    def available(self):
        info = self.request("GET", "/info")
        if info.get("OSType") != "linux" or any(
            "rootless" in item or "userns" in item for item in info.get("SecurityOptions", [])
        ):
            raise HostError("benchmark host requires rootful Linux Docker without user remapping")
        return info.get("ID")


@dataclass(frozen=True)
class ContainerOutcome:
    exit_code: int | None
    timed_out: bool = False
    session_died: bool = False

    @property
    def completed(self):
        return self.exit_code == 0 and not self.timed_out and not self.session_died

    def describe(self):
        return "timeout" if self.timed_out else "unobserved" if self.session_died else "exited"


class DockerHost:
    def __init__(
        self,
        document,
        image_id,
        run_dir,
        job_dir,
        *,
        engine=None,
        environ=None,
        user=None,
        run_id=None,
    ):
        self.document, self.runtime = document, document["runtime"]
        self.image_id = image_id
        self.run_id = run_id or Path(run_dir).name
        self.run_dir, self.job_dir = Path(run_dir).absolute(), Path(job_dir).absolute()
        self.engine = engine or DockerEngine()
        self.environ = os.environ if environ is None else environ
        self.uid, self.gid = os.geteuid(), os.getegid()
        if user is not None:
            if re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", user) is None:
                raise HostError("container user must be an explicit nonroot uid:gid")
            self.uid, self.gid = map(int, user.split(":"))
            if (self.uid, self.gid) != (os.geteuid(), os.getegid()):
                raise HostError("this host supports only the invoking account's allocated uid:gid")
        self.owner = str(uuid.uuid4())
        self.launch_id = str(uuid.uuid4())
        self.resources = []
        self.gate_image = None
        self.gate_commit_pending = False
        self.credential_files = []
        self.mounts = []
        self.sources = {}
        self.files = {}
        self.environment = dict(self.runtime["environment"])
        self.secrets = []
        self.input_hashes = {}
        self.container = None
        self.engine_id = None
        self.admit(document)

    @staticmethod
    def admit(document):
        runtime = document["runtime"]
        if document["mode"] != "automaton" or runtime["backend"] != "docker":
            raise HostError("unsupported capability: this benchmark host runs Docker Automatons")
        if runtime["network"]["mode"] not in {"none", "open"}:
            raise HostError("unsupported capability: restricted host networking")
        if runtime["plugins"] or runtime["lifecycle"]:
            raise HostError(
                "unsupported capability: host plugins and retained authentication lifecycle"
            )
        for credential in runtime["credentials"]:
            if credential["source"]["type"] != "raw" or credential["delivery"]["type"] == "relay":
                raise HostError("unsupported capability: provider or relay credentials")
        mounts = runtime["mounts"]
        if sum(row["purpose"] == "workspace" for row in mounts) != 1:
            raise HostError("benchmark requires one declared workspace mount")
        targets = []
        for row in mounts:
            if (
                row.get("exposure", "container") != "container"
                or row["source"]["kind"] != "runtime"
            ):
                raise HostError("unsupported capability: external or host-only mount")
            if row["persistent"]:
                raise HostError(
                    "unsupported capability: persistent mounts require operator-owned bindings"
                )
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", row["source"]["value"]) is None or row[
                "source"
            ]["value"] in {".", ".."}:
                raise HostError("unsupported runtime storage key")
            target = PurePosixPath(row["target"])
            if any(
                target == old or target in old.parents or old in target.parents for old in targets
            ):
                raise HostError("unsupported capability: overlapping mount layout")
            targets.append(target)
        files = {row["name"]: row for row in runtime["files"]}
        if (
            files.get("prompt", {}).get("direction") != "input"
            or files.get("proposal", {}).get("direction") != "output"
        ):
            raise HostError("benchmark requires declared prompt input and proposal output files")
        roles = {row["name"]: row for row in mounts}
        if (
            roles[files["prompt"]["mount"]]["purpose"] != "input"
            or roles[files["proposal"]["mount"]]["purpose"] != "output"
        ):
            raise HostError("prompt/proposal files must use declared input/output mounts")
        if (
            roles[files["proposal"]["mount"]]["access"] != "read_write"
            or next(row for row in mounts if row["purpose"] == "workspace")["access"]
            != "read_write"
        ):
            raise HostError("benchmark workspace and proposal output must be writable")
        destinations = set()
        bindings = {}
        for credential in runtime["credentials"]:
            source = credential["source"]["secret"]
            key = source.upper().replace("-", "_").replace(".", "_")
            if key in bindings and bindings[key] != source:
                raise HostError("ambiguous raw-secret environment binding")
            bindings[key] = source
            delivery = credential["delivery"]
            destination = (
                delivery["type"],
                delivery.get("variable"),
                delivery.get("mount"),
                delivery.get("path"),
            )
            if destination in destinations:
                raise HostError("duplicate credential destination")
            destinations.add(destination)
        bootstrap = runtime["bootstrap"]
        if bootstrap and bootstrap["protocol"] not in {"identity-v1", "identity-v2"}:
            raise HostError("unsupported bootstrap protocol")

    def _save(self):
        atomic_write(
            self.run_dir / "host-state.json",
            json.dumps(
                {
                    "version": 1,
                    "owner": self.owner,
                    "run_id": self.run_id,
                    "gate_commit_pending": self.gate_commit_pending,
                    "credential_files": self.credential_files,
                    "image_id": self.image_id,
                    "engine_id": self.engine_id,
                    "resources": self.resources,
                    "gate_image": self.gate_image,
                },
                sort_keys=True,
            ),
        )

    def redact(self, value):
        for secret in sorted(set(self.secrets), key=len, reverse=True):
            value = value.replace(secret, "[redacted credential]")
        return value

    def file_target(self, name):
        row = next(row for row in self.runtime["files"] if row["name"] == name)
        mount = next(mount for mount in self.runtime["mounts"] if mount["name"] == row["mount"])
        return str(PurePosixPath(mount["target"]) / row["path"])

    def prepare(self, render_prompt, request_metadata):
        self.engine_id = self.engine.available()
        self._save()
        for row in self.runtime["mounts"]:
            if row["purpose"] == "workspace":
                source = self.job_dir / "checkout"
                self.workdir = row["target"]
            elif row["purpose"] in {"input", "output"}:
                source = self.job_dir / row["purpose"]
            else:
                source = self.job_dir / "mounts" / row["name"]
            source.mkdir(parents=True, exist_ok=True, mode=0o700)
            if source.resolve() != source or source.stat().st_uid != os.geteuid():
                raise HostError("unsafe runtime mount source")
            self.sources[row["name"]] = source
            self.mounts.append(
                {
                    "Type": "bind",
                    "Source": str(source),
                    "Target": row["target"],
                    "ReadOnly": row["access"] == "read_only",
                }
            )
        for row in self.runtime["files"]:
            path = self.sources[row["mount"]] / row["path"]
            if path.parent.resolve() != path.parent or path.is_symlink():
                raise HostError("unsafe declared file backing")
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.files[row["name"]] = path
        prompt_file = next(row for row in self.runtime["files"] if row["name"] == "prompt")
        proposal_target = self.file_target("proposal")
        input_target = next(
            row["target"] for row in self.runtime["mounts"] if row["name"] == prompt_file["mount"]
        )
        prompt = render_prompt(input_target, proposal_target)
        validate_payload(prompt_file["schema"], prompt)
        atomic_write(self.files["prompt"], prompt)
        if "request" in self.files:
            declaration = next(row for row in self.runtime["files"] if row["name"] == "request")
            value = dict(
                request_metadata,
                prompt_path=self.file_target("prompt"),
                proposal_path=proposal_target,
                workspace_path=self.workdir,
            )
            validate_payload(declaration["schema"], value)
            atomic_write(self.files["request"], json.dumps(value, sort_keys=True))
        for row in self.runtime["credentials"]:
            key = row["source"]["secret"].upper().replace("-", "_").replace(".", "_")
            value = self.environ.get(key)
            if (
                not isinstance(value, str)
                or not value
                or len(value.encode()) > 65536
                or "\0" in value
            ):
                raise HostError("required raw-secret binding is unavailable")
            self.secrets.append(value)
            delivery = row["delivery"]
            if delivery["type"] == "environment":
                self.environment[delivery["variable"]] = value
            else:
                mount = next(m for m in self.runtime["mounts"] if m["name"] == delivery["mount"])
                target = str(PurePosixPath(mount["target"]) / delivery["path"])
                if target in {self.file_target(f["name"]) for f in self.runtime["files"]}:
                    raise HostError("credential delivery conflicts with a declared file surface")
                placeholder = self.sources[delivery["mount"]] / delivery["path"]
                if not placeholder.exists():
                    atomic_write(placeholder, b"")
                elif placeholder.is_symlink() or not placeholder.is_file():
                    raise HostError("unsafe credential mountpoint")
                private = self.run_dir / ".credentials" / row["name"]
                self.credential_files.append(row["name"])
                self._save()
                atomic_write(private, value)
                self.mounts.append(
                    {"Type": "bind", "Source": str(private), "Target": target, "ReadOnly": True}
                )
        bootstrap = self.runtime["bootstrap"]
        if bootstrap:
            by_target = {self.file_target(name): path for name, path in self.files.items()}
            self.handoff = by_target[bootstrap["handoff"]]
            for target in (bootstrap["identity_input"], bootstrap["handoff"]):
                placeholder = by_target[target]
                if not placeholder.exists():
                    atomic_write(placeholder, b"")
            input_file = self.run_dir / ".bootstrap" / "identity.json"
            atomic_write(
                input_file,
                json.dumps(
                    {
                        "version": 1,
                        "launch_id": self.launch_id,
                        "uid": self.uid,
                        "gid": self.gid,
                        "sudo": self.runtime["sudo"],
                        "home": bootstrap["home"],
                        "shell": bootstrap["shell"],
                    }
                ),
            )
            self.mounts.append(
                {
                    "Type": "bind",
                    "Source": str(input_file),
                    "Target": bootstrap["identity_input"],
                    "ReadOnly": True,
                }
            )
            if bootstrap["protocol"] == "identity-v2":
                self.handoff = self.run_dir / ".bootstrap" / "handoff.json"
                atomic_write(self.handoff, b"")
                self.mounts.append(
                    {
                        "Type": "bind",
                        "Source": str(self.handoff),
                        "Target": bootstrap["handoff"],
                        "ReadOnly": False,
                    }
                )
            else:
                backing = next(
                    m
                    for m in self.runtime["mounts"]
                    if PurePosixPath(bootstrap["handoff"]).is_relative_to(m["target"])
                )
                if backing["persistent"]:
                    raise HostError("identity-v1 needs launch-private handoff storage")
                self.handoff.unlink(missing_ok=True)
            self.environment.update(HOME=bootstrap["home"], SHELL=bootstrap["shell"])
        bootstrap_paths = (
            {bootstrap[k] for k in ("identity_input", "handoff")} if bootstrap else set()
        )
        for row in self.runtime["files"]:
            if row["direction"] == "input" and self.file_target(row["name"]) not in bootstrap_paths:
                data = read_regular(self.files[row["name"]], 16 * 1024 * 1024)
                self.input_hashes[row["name"]] = "sha256:" + hashlib.sha256(data).hexdigest()
                atomic_write(self.run_dir / "trusted-input" / row["name"], data)
        self._save()

    def _owned(self, resource):
        found = self.engine.inspect(resource["id"] or resource["name"])
        if found is not None and (
            found.get("Config", {}).get("Labels", {}).get(OWNER_LABEL) != self.owner
            or found.get("Config", {}).get("Labels", {}).get(ROLE_LABEL) != resource["role"]
            or found.get("Image") != resource["image"]
            or (resource["id"] is not None and found.get("Id") != resource["id"])
        ):
            raise HostError("container ownership changed; refusing mutation")
        return found

    def _create(self, argv, *, image, role, root_bootstrap=False):
        resource = {
            "name": container_name(self.run_id)
            if role == "workload"
            else "silverquillm-gate-" + uuid.uuid4().hex,
            "id": None,
            "image": image,
            "role": role,
        }
        self.resources.append(resource)
        self._save()
        host = {
            "Mounts": self.mounts,
            "NetworkMode": self.runtime["network"]["mode"]
            if self.runtime["network"]["mode"] == "none"
            else "bridge",
            "RestartPolicy": {"Name": "no"},
            "LogConfig": {"Type": "local", "Config": {"max-size": "16m", "max-file": "2"}},
        }
        if not self.runtime["sudo"]:
            host["SecurityOpt"] = ["no-new-privileges"]
        limits = self.runtime["resources"]
        if limits["cpus"] is not None:
            host["NanoCpus"] = int(limits["cpus"] * 1e9)
        if limits["memory_bytes"] is not None:
            host.update(Memory=limits["memory_bytes"], MemorySwap=limits["memory_bytes"])
        if limits["pids"] is not None:
            host["PidsLimit"] = limits["pids"]
        result = self.engine.request(
            "POST",
            "/containers/create?name=" + resource["name"],
            {
                "Image": image,
                "Entrypoint": [argv[0]],
                "Cmd": argv[1:],
                "WorkingDir": self.workdir,
                "User": "0:0" if root_bootstrap else f"{self.uid}:{self.gid}",
                "Env": [key + "=" + value for key, value in sorted(self.environment.items())],
                "Labels": {OWNER_LABEL: self.owner, ROLE_LABEL: role},
                "HostConfig": host,
            },
        )
        identifier = result.get("Id")
        if not isinstance(identifier, str) or re.fullmatch(r"[0-9a-f]{64}", identifier) is None:
            raise HostError("container create returned invalid identity")
        resource["id"] = identifier
        self._save()
        self._owned(resource)
        self.engine.request("POST", "/containers/" + identifier + "/start")
        return resource

    def _stop(self, resource):
        found = self._owned(resource)
        if found is not None and found["State"]["Running"]:
            self.engine.request("POST", "/containers/" + found["Id"] + "/stop?t=2")
            found = self._owned(resource)
        if found is not None and found["State"]["Running"]:
            raise HostError("container stop is unconfirmed")
        return found

    def _wait(self, resource, timeout):
        deadline = time.monotonic() + timeout
        while True:
            found = self._owned(resource)
            if found is None:
                raise HostError("owned container disappeared without an outcome")
            if not found["State"]["Running"]:
                return ContainerOutcome(found["State"].get("ExitCode"))
            if time.monotonic() >= deadline:
                stopped = self._stop(resource)
                return ContainerOutcome(
                    (stopped or {}).get("State", {}).get("ExitCode"), timed_out=True
                )
            time.sleep(0.05)

    def _logs(self, resource):
        raw = self.engine.request(
            "GET",
            "/containers/" + resource["id"] + "/logs?stdout=1&stderr=1",
            raw=True,
            maximum=MAX_LOG_BYTES,
        )
        channels = {1: bytearray(), 2: bytearray()}
        while raw:
            if len(raw) < 8 or raw[0] not in channels or raw[1:4] != b"\0\0\0":
                raise HostError("invalid Docker output framing")
            size = int.from_bytes(raw[4:8], "big")
            if len(raw) < 8 + size:
                raise HostError("truncated Docker output framing")
            channels[raw[0]].extend(raw[8 : 8 + size])
            raw = raw[8 + size :]
        return {
            name: self.redact(bytes(channels[number]).decode(errors="replace"))
            for number, name in ((1, "stdout"), (2, "stderr"))
        }

    def run(self, timeout):
        argv = list(self.runtime["main"])
        if self.runtime["initializer"] is not None:
            argv = [
                *self.runtime["initializer_runner"],
                "--initializer-json",
                json.dumps(self.runtime["initializer"]),
                "--",
                *argv,
            ]
        bootstrap = self.runtime["bootstrap"]
        if bootstrap:
            argv = [
                *bootstrap["argv"],
                "--identity-input",
                bootstrap["identity_input"],
                "--handoff",
                bootstrap["handoff"],
                *(["--protocol", "identity-v2"] if bootstrap["protocol"] == "identity-v2" else []),
                "--",
                *argv,
            ]
        self.container = self._create(
            argv, image=self.image_id, role="workload", root_bootstrap=bool(bootstrap)
        )
        budget = min(timeout, self.runtime["timeout_seconds"] or timeout)
        outcome = self._wait(self.container, budget)
        for channel, output in self._logs(self.container).items():
            atomic_write(self.run_dir / ("container-" + channel + ".txt"), output)
        if bootstrap and not outcome.timed_out:
            raw = read_regular(self.handoff, 65536)
            expected = {
                "version": 2 if bootstrap["protocol"] == "identity-v2" else 1,
                "launch_id": self.launch_id,
                "uid": self.uid,
                "gid": self.gid,
            }
            observed = json.loads(raw)
            if (
                observed != expected
                or any(type(observed[k]) is not int for k in ("version", "uid", "gid"))
                or (bootstrap["protocol"] == "identity-v2" and not raw.endswith(b"\n"))
            ):
                raise HostError("current-launch identity handoff is unconfirmed")
        return outcome

    def gate(self, command, timeout):
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= 3600
        ):
            raise HostError("invalid isolated gate deadline")
        if self.gate_image is None:
            if self.container is None or self._stop(self.container) is None:
                raise HostError("gate requires the stopped owned workload")
            self.gate_commit_pending = True
            self._save()
            result = self.engine.request(
                "POST",
                "/commit?container=" + self.container["id"] + "&pause=false",
                {"Labels": {OWNER_LABEL: self.owner, ROLE_LABEL: "gate-image"}},
            )
            self.gate_image = result["Id"]
            self.gate_commit_pending = False
            self._save()
        resource = self._create(["/bin/sh", "-lc", command], image=self.gate_image, role="gate")
        outcome = self._wait(resource, timeout)
        logs = self._logs(resource)
        return outcome.completed, logs["stdout"] + logs["stderr"]

    def finish(self):
        state = recover_resources(self.run_dir, self.run_id, engine=self.engine)
        if state is not None:
            self.resources = state["resources"]
            self.gate_image = state["gate_image"]
            self.gate_commit_pending = state["gate_commit_pending"]
            self.credential_files = state["credential_files"]
        self.environment.clear()
        self.secrets.clear()


def recover_resources(run_dir, run_id, *, engine=None):
    """Reconcile the durable resource inventory before any workspace is harvested."""
    engine = engine or DockerEngine()
    run_dir = Path(run_dir).absolute()
    state_path = run_dir / "host-state.json"
    try:
        state = json.loads(read_regular(state_path))
    except FileNotFoundError:
        if engine.inspect(container_name(run_id)) is not None:
            raise HostError("container exists without a trusted resource inventory")
        return None
    except (OSError, ValueError):
        raise HostError("resource inventory is unreadable") from None
    fields = {
        "version",
        "owner",
        "run_id",
        "image_id",
        "engine_id",
        "resources",
        "gate_image",
        "gate_commit_pending",
        "credential_files",
    }
    image_pattern = r"sha256:[0-9a-f]{64}"
    try:
        if not (isinstance(state, dict) and set(state) == fields):
            raise ValueError("invalid resource inventory")
        if not (type(state["version"]) is int and state["version"] == 1):
            raise ValueError("invalid resource inventory")
        if not (str(uuid.UUID(state["owner"])) == state["owner"]):
            raise ValueError("invalid resource inventory")
        if not (state["run_id"] == run_id):
            raise ValueError("invalid resource inventory")
        if not (re.fullmatch(image_pattern, state["image_id"])):
            raise ValueError("invalid resource inventory")
        if not (type(state["gate_commit_pending"]) is bool):
            raise ValueError("invalid resource inventory")
        if not (isinstance(state["resources"], list)):
            raise TypeError("invalid resource inventory")
        if not (isinstance(state["credential_files"], list)):
            raise TypeError("invalid resource inventory")
        if not (len(set(state["credential_files"])) == len(state["credential_files"])):
            raise ValueError("invalid resource inventory")
        if not (
            all(
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name)
                for name in state["credential_files"]
            )
        ):
            raise ValueError("invalid resource inventory")
        names = set()
        for resource in state["resources"]:
            if not (
                set(resource)
                in ({"name", "id", "image", "role"}, {"name", "id", "image", "role", "removed"})
            ):
                raise ValueError("invalid resource inventory")
            if not (resource["role"] in {"workload", "gate"}):
                raise ValueError("invalid resource inventory")
            if not (resource["name"] not in names):
                raise ValueError("invalid resource inventory")
            names.add(resource["name"])
            if not (
                resource["name"] == container_name(run_id)
                if resource["role"] == "workload"
                else re.fullmatch(r"silverquillm-gate-[0-9a-f]{32}", resource["name"])
            ):
                raise ValueError("invalid resource inventory")
            if not (resource["id"] is None or re.fullmatch(r"[0-9a-f]{64}", resource["id"])):
                raise ValueError("invalid resource inventory")
            if not (re.fullmatch(image_pattern, resource["image"])):
                raise ValueError("invalid resource inventory")
            if not (type(resource.get("removed", False)) is bool):
                raise ValueError("invalid resource inventory")
            if not (
                resource["image"]
                == (state["image_id"] if resource["role"] == "workload" else state["gate_image"])
            ):
                raise ValueError("invalid resource inventory")
        gate_image = state["gate_image"]
        if not (
            gate_image is None
            or (re.fullmatch(image_pattern, gate_image) and gate_image != state["image_id"])
        ):
            raise ValueError("invalid resource inventory")
    except (AssertionError, KeyError, TypeError, ValueError):
        raise HostError("resource inventory is malformed; refusing mutation") from None
    if engine.available() != state["engine_id"]:
        raise HostError("resource inventory belongs to a different Docker engine")

    def save():
        atomic_write(state_path, json.dumps(state, sort_keys=True))

    def owned(resource):
        found = engine.inspect(resource["id"] or resource["name"])
        if found is None:
            if resource["id"] is None:
                raise HostError("container creation is unconfirmed; retain the resource inventory")
            return None
        labels = found.get("Config", {}).get("Labels", {})
        if (
            labels.get(OWNER_LABEL) != state["owner"]
            or labels.get(ROLE_LABEL) != resource["role"]
            or found.get("Image") != resource["image"]
            or resource["id"] is not None
            and found.get("Id") != resource["id"]
        ):
            raise HostError("container ownership changed; refusing mutation")
        return found

    def owned_image(identifier):
        found = engine.request(
            "GET", "/images/" + quote(identifier, safe="") + "/json", missing=True
        )
        if found is not None:
            labels = found.get("Config", {}).get("Labels", {})
            if (
                found.get("Id") != identifier
                or labels.get(OWNER_LABEL) != state["owner"]
                or labels.get(ROLE_LABEL) != "gate-image"
            ):
                raise HostError("gate image ownership changed; refusing mutation")
        return found

    # Check the entire inventory before the first resource mutation.
    for resource in state["resources"]:
        owned(resource)
    if state["gate_commit_pending"]:
        filters = json.dumps(
            {"label": [OWNER_LABEL + "=" + state["owner"], ROLE_LABEL + "=gate-image"]}
        )
        matches = engine.request("GET", "/images/json?all=true&filters=" + quote(filters, safe=""))
        if len(matches) != 1 or matches[0]["Id"] == state["image_id"]:
            raise HostError("gate snapshot creation is unconfirmed; retain the resource inventory")
        state["gate_image"] = matches[0]["Id"]
        owned_image(state["gate_image"])
        state["gate_commit_pending"] = False
        save()
    if state["gate_image"] is not None:
        owned_image(state["gate_image"])
    for resource in reversed(state["resources"]):
        found = owned(resource)
        if found is not None:
            resource["id"] = found["Id"]
            save()
            if found["State"]["Running"]:
                engine.request("POST", "/containers/" + found["Id"] + "/stop?t=2")
                found = owned(resource)
            if found is not None and found["State"]["Running"]:
                raise HostError("container stop is unconfirmed")
            if found is not None:
                engine.request("DELETE", "/containers/" + found["Id"] + "?v=1")
            if owned(resource) is not None:
                raise HostError("container removal is unconfirmed")
        resource["removed"] = True
        save()
    if state["gate_image"] is not None:
        if owned_image(state["gate_image"]) is not None:
            engine.request(
                "DELETE", "/images/" + quote(state["gate_image"], safe="") + "?noprune=1"
            )
        if owned_image(state["gate_image"]) is not None:
            raise HostError("gate image removal is unconfirmed")
        # Retain the identity for checking historical removed gate containers.
    private = run_dir / ".credentials"
    if private.exists() and private.resolve() != private:
        raise HostError("unsafe credential cleanup directory")
    for name in state["credential_files"]:
        (private / name).unlink(missing_ok=True)
    state["credential_files"] = []
    save()
    return state
