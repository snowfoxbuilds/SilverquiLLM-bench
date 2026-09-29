"""Karn v4 artifact intake; no builder or Ozolith daemon imports."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

MAX_DOCUMENT = 1024 * 1024
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class KarnError(ValueError):
    """A concrete intake or host failure with no credential values in its message."""


def strict_json(raw: bytes) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise KarnError("duplicate_json_key")
            result[key] = value
        return result

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise KarnError("nonfinite_json_number")
        return value

    def constant(_):
        raise KarnError("nonfinite_json_number")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, KarnError):
            raise
        raise KarnError("invalid_json") from None


def canonical(value: object, *, ascii_only: bool = False) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii_only, allow_nan=False
        ).encode("utf-8")
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise KarnError("invalid_canonical_json") from None


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_regular(path: Path, *, limit: int = MAX_DOCUMENT) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
                raise KarnError("unsafe_artifact_file")
            value = stream.read(limit + 1)
            if len(value) > limit:
                raise KarnError("artifact_file_too_large")
            return value
    except OSError:
        raise KarnError("artifact_file_unavailable") from None


def tree_digest(source: Path, *, limit: int = 256 * 1024 * 1024) -> str:
    """Digest a file or directory tree by relative path and content."""
    paths = sorted(source.rglob("*")) if source.is_dir() else [source]
    content = [
        [
            str(path.relative_to(source)) if path != source else source.name,
            digest(read_regular(path, limit=limit)),
        ]
        for path in paths
        if not path.is_dir()
    ]
    return digest(canonical(content))


def inside(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or "\0" in relative
        or path.is_absolute()
        or any(p in ("", ".", "..") for p in relative.split("/"))
    ):
        raise KarnError("unsafe_artifact_path")
    result = root.joinpath(*path.parts)
    if any(part.is_symlink() for part in (result, *result.parents) if part != root.parent):
        raise KarnError("symlink_artifact_path")
    try:
        result.resolve().relative_to(root.resolve())
    except ValueError:
        raise KarnError("artifact_path_escapes_root") from None
    return result


def _guest_path(value: str) -> str:
    if (
        not value.startswith("/")
        or value == "/"
        or "\\" in value
        or any(ord(c) < 32 for c in value)
    ):
        raise KarnError("unsafe_guest_path")
    if any(p in ("", ".", "..") for p in value.split("/")[1:]):
        raise KarnError("unsafe_guest_path")
    return value


def decode_definition(raw: bytes) -> dict:
    if len(raw) > MAX_DOCUMENT:
        raise KarnError("definition_size_limit")
    document = strict_json(raw)
    schema = json.loads(files(__package__).joinpath("definition-v4.schema.json").read_bytes())
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path)
        raise KarnError("invalid_definition" + (":" + location if location else ""))
    try:
        if str(uuid.UUID(document["definition_id"])) != document["definition_id"]:
            raise ValueError
    except ValueError:
        raise KarnError("noncanonical_definition_id") from None
    runtime = document["runtime"]
    for group in ("mounts", "files", "plugins", "credentials"):
        key = "id" if group == "plugins" else "name"
        names = [row[key] for row in runtime[group]]
        if len(set(names)) != len(names):
            raise KarnError("duplicate_runtime_" + group)
    mounts = {row["name"]: row for row in runtime["mounts"]}
    targets = []
    for row in mounts.values():
        if row.get("exposure", "container") == "container":
            targets.append(_guest_path(row["target"]))
    if len(set(targets)) != len(targets):
        raise KarnError("duplicate_mount_target")
    for row in runtime["files"]:
        mount = mounts.get(row["mount"])
        if mount is None or mount.get("exposure", "container") != "container":
            raise KarnError("invalid_file_mount")
        inside(Path("/declared-mount"), row["path"])
    initializer_runner = runtime.get("initializer_runner")
    if (runtime["initializer"] is None) != (initializer_runner is None):
        raise KarnError("initializer_runner_required")
    surfaces = {}
    for row in runtime["files"]:
        target = str(PurePosixPath(mounts[row["mount"]]["target"]) / row["path"])
        if target in surfaces:
            raise KarnError("duplicate_file_surface")
        surfaces[target] = row
        if row["direction"] in ("output", "status"):
            effective = max(
                (
                    m
                    for m in mounts.values()
                    if m.get("exposure", "container") == "container"
                    and PurePosixPath(target).is_relative_to(m["target"])
                ),
                key=lambda m: len(PurePosixPath(m["target"]).parts),
            )
            if effective["access"] == "read_only":
                raise KarnError("read_only_output_surface")
        try:
            Draft202012Validator.check_schema(row["schema"])
        except SchemaError:
            raise KarnError("invalid_payload_schema") from None
    bootstrap = runtime["bootstrap"]
    if bootstrap:
        for key in ("identity_input", "handoff", "home", "shell"):
            _guest_path(bootstrap[key])
        if (
            bootstrap["identity_input"] == bootstrap["handoff"]
            or surfaces.get(bootstrap["identity_input"], {}).get("direction") != "input"
            or surfaces.get(bootstrap["handoff"], {}).get("direction") != "status"
        ):
            raise KarnError("undeclared_bootstrap_surface")
    if any("\0" in value for value in runtime["environment"].values()):
        raise KarnError("invalid_runtime_environment")
    network = runtime["network"]
    if network["mode"] != "restricted" and network["https_hosts"]:
        raise KarnError("unexpected_network_allowlist")
    if any(
        host != host.lower() or not host.isascii() or any(c in host for c in "/:@* ")
        for host in network["https_hosts"]
    ):
        raise KarnError("invalid_https_host")
    for row in runtime["credentials"]:
        source, delivery = row["source"], row.get("delivery")
        if source["type"] == "provider" and source["plugin"] not in {
            p["id"] for p in runtime["plugins"]
        }:
            raise KarnError("unknown_provider_plugin")
        if delivery and delivery["type"] == "file":
            if (
                delivery["mount"] not in mounts
                or mounts[delivery["mount"]].get("exposure", "container") != "container"
            ):
                raise KarnError("invalid_credential_mount")
            inside(Path("/declared-mount"), delivery["path"])
    commands = [runtime["main"], runtime["initializer"], initializer_runner]
    if bootstrap:
        commands.append(bootstrap["argv"])
    for argv in commands:
        if argv is not None and (not argv[0] or any("\0" in part for part in argv)):
            raise KarnError("invalid_runtime_command")
    canonical(document)
    return document


@dataclass(frozen=True)
class PluginArtifact:
    row: dict
    manifest: dict
    install_path: Path
    wheels: tuple[tuple[Path, str], ...]
    data_path: Path | None

    def verify(self) -> None:
        if digest(canonical(self.manifest, ascii_only=True)) != self.row["artifact"]:
            raise KarnError("plugin_manifest_changed")
        for path, expected in self.wheels:
            if digest(read_regular(path, limit=256 * 1024 * 1024)) != expected:
                raise KarnError("plugin_wheel_digest_mismatch")


@dataclass(frozen=True)
class KarnCandidate:
    build_output: Path
    definition_path: Path
    definition: dict
    canonical_bytes: bytes
    definition_digest: str
    image_id: str
    plugins: tuple[PluginArtifact, ...]
    # The image's labels as inspected at load, e.g. Karn's recipe revision.
    image_labels: dict = field(default_factory=dict, compare=False)

    @property
    def image(self) -> str:
        return self.definition["image"]

    @property
    def definition_id(self) -> str:
        return self.definition["definition_id"]

    @property
    def runtime(self) -> dict:
        return self.definition["runtime"]

    def identity(self) -> dict:
        return {
            "definition_version": 4,
            "definition_id": self.definition_id,
            "definition_digest": self.definition_digest,
            "image": self.image,
            "image_id": self.image_id,
        }

    def verify(self, image_inspector: Callable[[str], dict] | None = None) -> None:
        if canonical(self.definition) != self.canonical_bytes:
            raise KarnError("candidate_definition_changed")
        if canonical(decode_definition(read_regular(self.definition_path))) != self.canonical_bytes:
            raise KarnError("candidate_artifact_changed")
        for plugin in self.plugins:
            plugin.verify()
        if (
            image_inspector is not None
            and _verify_image(self.image, image_inspector(self.image)) != self.image_id
        ):
            raise KarnError("candidate_image_changed")


def inspect_image(reference: str) -> dict:
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", reference], capture_output=True, check=False, timeout=30
        )
        if result.returncode:
            # Any other failure, such as no permission on the Docker socket, says nothing
            # about whether the image exists.
            if b"no such image" in result.stderr.lower():
                raise KarnError("image_not_available_locally")
            raise KarnError("docker_unavailable")
        rows = strict_json(result.stdout)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise KarnError("invalid_image_inspection")
        return rows[0]
    except (OSError, subprocess.TimeoutExpired):
        raise KarnError("image_inspection_failed") from None


def _verify_image(reference: str, inspection: dict) -> str:
    image_id = inspection.get("Id")
    if not isinstance(image_id, str) or not DIGEST.fullmatch(image_id):
        raise KarnError("invalid_image_id")
    if reference.startswith("sha256:"):
        if image_id != reference:
            raise KarnError("image_identity_mismatch")
    elif reference not in inspection.get("RepoDigests", []):
        raise KarnError("image_repository_digest_mismatch")
    return image_id


def _plugin(root: Path, construct: Path, row: dict) -> PluginArtifact:
    install_path = inside(root, f"plugins/{row['id']}-{row['version']}/install.json")
    document = strict_json(read_regular(install_path))
    if not isinstance(document, dict) or set(document) != {"manifest", "locations"}:
        raise KarnError("invalid_plugin_install_document")
    manifest, locations = document["manifest"], document["locations"]
    if (
        not isinstance(manifest, dict)
        or digest(canonical(manifest, ascii_only=True)) != row["artifact"]
    ):
        raise KarnError("plugin_manifest_digest_mismatch")
    required = {"id", "version", "sdk_major", "python", "module", "hooks", "wheels"}
    if (
        not required <= manifest.keys()
        or manifest["id"] != row["id"]
        or manifest["version"] != row["version"]
    ):
        raise KarnError("plugin_identity_mismatch")
    if (
        manifest["sdk_major"] != 1
        or not isinstance(manifest["hooks"], list)
        or not all(isinstance(hook, str) for hook in manifest["hooks"])
        or not isinstance(manifest["module"], str)
        or not all(part.isidentifier() for part in manifest["module"].split("."))
    ):
        raise KarnError("invalid_plugin_manifest")
    wheels = manifest["wheels"]
    if (
        not isinstance(wheels, dict)
        or not wheels
        or not isinstance(locations, dict)
        or set(locations) != set(wheels)
    ):
        raise KarnError("invalid_plugin_wheel_closure")
    paths = []
    for name, expected in wheels.items():
        if (
            not isinstance(name, str)
            or "/" in name
            or not name.endswith(".whl")
            or not isinstance(expected, str)
            or not DIGEST.fullmatch(expected)
            or not isinstance(locations[name], str)
        ):
            raise KarnError("invalid_plugin_wheel")
        path = inside(install_path.parent, locations[name])
        if path.name != name:
            raise KarnError("plugin_wheel_filename_mismatch")
        paths.append((path, expected))
    data = inside(construct, f"plugin-data/{row['id']}")
    artifact = PluginArtifact(
        row, manifest, install_path, tuple(paths), data if data.exists() else None
    )
    artifact.verify()
    return artifact


def load_candidate(
    build_output: Path | str,
    construct_name: str,
    *,
    image_inspector: Callable[[str], dict] = inspect_image,
) -> KarnCandidate:
    """Consume a completed build and a locally present exact image, without building/pulling."""
    root = Path(build_output).resolve()
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", construct_name):
        raise KarnError("invalid_construct_name")
    definition_path = inside(root, f"constructs/{construct_name}/definition.json")
    document = decode_definition(read_regular(definition_path))
    encoded = canonical(document)
    inspection = image_inspector(document["image"])
    image_id = _verify_image(document["image"], inspection)
    config = inspection.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    plugins = tuple(
        _plugin(root, definition_path.parent, row) for row in document["runtime"]["plugins"]
    )
    return KarnCandidate(
        root,
        definition_path,
        document,
        encoded,
        digest(encoded),
        image_id,
        plugins,
        dict(labels) if isinstance(labels, dict) else {},
    )
