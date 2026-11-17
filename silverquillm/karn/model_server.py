"""A local model server for pi constructs (issue #262).

A recipe that declares ``SILVERQUILLM_MODEL_SERVER`` in its runtime environment is served by
a llama.cpp ``llama-server`` the bench starts on the host, bound to loopback. The workload
reaches it only as ``http://model-server:8080/v1``: the per-run proxy sidecar forwards that
address to a host-side relay, and the relay forwards to the server and records every request.
The recipe's server settings are part of its definition, so each configuration is its own
candidate; the host config only says where this host keeps the builds and the model files.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import http.client
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .definition import KarnError
from .observations import TOKEN_KEYS, _measurements

MODEL_SERVER_ENV = "SILVERQUILLM_MODEL_SERVER"
MODEL_SERVER_HOST = "model-server"
MODEL_SERVER_PORT = 8080
MODEL_SERVER_URL = f"http://{MODEL_SERVER_HOST}:{MODEL_SERVER_PORT}/v1"
TELEMETRY_ADAPTER = "model_server"
THREAD_ID = "main"
EVENTS_FILE = "observations.events.jsonl"
TRANSCRIPT_FILE = "model-transcript.jsonl"
SERVER_LOG = "model-server.log"

# Flags the bench owns or that would defeat the record, refused anywhere in a recipe. A
# token is refused alone or as ``--flag=value``; every other flag passes, and is recorded
# with the rest of the recipe's arguments.
REFUSED_FLAGS = frozenset(
    {
        # The bench owns the address and the API surface the relay understands.
        *("--host", "--port", "--path", "--api-prefix", "--api-key", "--api-key-file"),
        *("--ui", "--webui", "--no-ui", "--no-webui", "--ui-config", "--webui-config"),
        *("--ui-config-file", "--webui-config-file", "--ssl-key-file", "--ssl-cert-file"),
        # The model's identity is the verified files and the bench's alias.
        *("-mu", "--model-url", "-dr", "--docker-repo", "-hf", "-hfr", "--hf-repo"),
        *("-hff", "--hf-file", "-hft", "--hf-token", "-hfd", "-hfrd", "--hf-repo-draft"),
        *("--spec-draft-hf", "-mmu", "--mmproj-url", "-a", "--alias"),
        *("--models-dir", "--models-preset"),
        # The server reaches no other host and runs nothing on this one for a request.
        *("--rpc", "--tools", "--tools-runtime", "--mcp-servers-config", "--mcp-servers-json"),
        *("--ui-mcp-proxy", "--webui-mcp-proxy", "--no-ui-mcp-proxy", "--no-webui-mcp-proxy"),
        # The server writes, and reads on a request's behalf, only where the bench puts it.
        *("--log-file", "--slot-save-path", "--log-prompts-dir", "--media-path"),
        *("--video-ffmpeg-dir", "-lcd", "--lookup-cache-dynamic"),
        # An agent mode, a tunnel, and a shared port all change who reaches the server.
        *("-ag", "--agent", "-no-ag", "--no-agent", "--connect", "--connect-code"),
        "--reuse-port",
        # b12182's presets download a model from Hugging Face and move the port.
        *("--embd-gemma-default", "--fim-qwen-1.5b-default", "--fim-qwen-3b-default"),
        *("--fim-qwen-7b-default", "--fim-qwen-7b-spec", "--fim-qwen-14b-spec"),
        *("--fim-qwen-30b-default", "--gpt-oss-20b-default", "--gpt-oss-120b-default"),
        *("--vision-gemma-4b-default", "--vision-gemma-12b-default"),
        # They take ``FNAME:SCALE``, which a ``files`` entry has no way to say.
        *("--lora-scaled", "--control-vector-scaled"),
    }
)
# llama.cpp b12182's flags naming an input file: refused among the arguments, since a file
# must be declared in ``files`` to be verified and recorded.
FILE_FLAGS = frozenset(
    {
        *("-m", "--model", "-md", "--model-draft", "--spec-draft-model", "-mm", "--mmproj"),
        *("--chat-template-file", "--grammar-file", "-jf", "--json-schema-file"),
        *("-lcs", "--lookup-cache-static", "--lora", "--control-vector"),
        *("-f", "--file", "-bf", "--binary-file"),
    }
)
MODEL_FLAG = "--model"
# Variables llama.cpp b12182 reads as options, a port, a route, a config, cache or download
# location, or a library path, and the ones the bench itself sets: the GPU Slot owns which
# GPUs the server sees, and the bench owns PATH, HOME and the XDG directories.
# libcuda, cuBLAS and the TLS library read some as code to load or a file to write.
REFUSED_ENVIRONMENT_PREFIXES = (
    *("LLAMA_", "LLAMACPP_", "AIP_", "LD_", "XDG_", "HF_", "HUGGING_FACE_", "HUGGINGFACE_"),
    *("OPENSSL_", "SSL_CERT_", "__"),
)
REFUSED_ENVIRONMENT = frozenset(
    {
        *("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "PATH", "HOME"),
        # Other backends' GPU selection: GPU Slots pin CUDA builds only.
        *("GGML_VK_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES"),
        *("GGML_BACKEND_PATH", "GGML_ET_KERNELS_PATH", "GGML_OPENCL_KERNEL_CACHE_DIR"),
        *("GGML_ET_PROFILE", "ET_TOOLCHAIN", "TOOLCHAIN_ROOT"),
        *("MODEL_ENDPOINT", "MTMD_BACKEND_DEVICE", "MTMD_DEBUG_EMBEDDINGS"),
        *("CUDA_INJECTION64_PATH", "CUDA_INJECTION32_PATH", "CUDA_AMODEL_DLL"),
        *("CUDA_FORCE_PRELOAD_LIBRARIES", "CUDA_DEVCODE_PATH", "CUDA_CACHE_PATH"),
        *("CUDA_MPS_PIPE_DIRECTORY", "CUDA_MPS_LOG_DIRECTORY", "GCONV_PATH"),
    }
)
# Any log file, log destination or core dump is a write to a host path.
REFUSED_ENVIRONMENT_PATTERN = re.compile(r".*(_LOG_FILE|LOGDEST|COREDUMP).*")
REFUSED_ENVIRONMENT_ANY_CASE = frozenset({"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"})
# A dynamically linked build may need this one on its host; a recipe never sets it.
HOST_ONLY_ENVIRONMENT = frozenset({"LD_LIBRARY_PATH"})
# llama.cpp reads these whatever the environment says; the bench cannot point them elsewhere.
SYSTEM_CONFIG_FILES = (Path("/etc/llama.cpp/config.ini"),)
DEFAULT_READY_SECONDS = 900
DEFAULT_REQUEST_TIMEOUT_SECONDS = 1800
MAX_TIMEOUT_SECONDS = 86400
_BUILD = re.compile(r"b([0-9]{1,8})")
_VERSION = re.compile(r"build ([0-9]{1,8}), commit ([0-9a-f]{7,40})")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}")
_SHARD = re.compile(r"(.+)-([0-9]{5})-of-([0-9]{5})\.gguf")
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
# A request at the largest context is a few MiB; the cap also bounds the parse here and the
# sidecar's copy, which runs in 128 MiB.
MAX_REQUEST_BYTES = 16 * 1024 * 1024
# What the relay keeps of workload-controlled request content, per field and per request.
MAX_KEPT_FIELD_CHARS = 4096
MAX_KEPT_MESSAGES_CHARS = 1024 * 1024
# Request keys pi sends; any other is a per-request override of the recipe's server settings.
ORDINARY_REQUEST_KEYS = frozenset(
    {"model", "messages", "tools", "stream", "stream_options", "store", "max_completion_tokens"}
)
# How long finalizing waits for cancelled requests to write their terminal records. A request
# still unsettled after it is counted from its start record as unfinished.
SETTLE_SECONDS = 10
REQUEST_STARTED = "request_started"
TRANSCRIPT_LOST = "transcript_lost"
RELAYED_PATHS = {("POST", "/v1/chat/completions"), ("GET", "/v1/models")}
# A GPU with more memory in use than this runs someone's job, even when ``nvidia-smi`` lists
# no process to this user; an idle card uses tens of MiB.
BUSY_MEMORY_MIB = 1024
NVIDIA_SMI_SECONDS = 10
GPU_QUERY = "index,uuid,name,memory.used,memory.total,power.limit,driver_version"
# The runner's GPU selection, which a host without GPU Slots passes on to its server.
GPU_SELECTION = ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER")


@dataclass(frozen=True)
class ServerFile:
    """One input file the server reads, verified by its digest; passed after ``flag``, if any."""

    file: str
    sha256: str
    flag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        entry = {"file": self.file, "sha256": self.sha256}
        return entry if self.flag is None else {**entry, "flag": self.flag}


@dataclass(frozen=True)
class ModelServerSpec:
    """The recipe's server: an engine build, its files, the server flags and settings.

    A setting the recipe leaves out is absent from :meth:`to_dict`, so a recipe written before
    it existed records exactly what it always did.
    """

    engine: str
    build: str
    model_file: str
    model_sha256: str
    arguments: tuple[str, ...]
    served_model: str
    files: tuple[ServerFile, ...] = ()
    """The declared ``files``, the model among them; empty for a recipe naming one ``model``."""
    environment: tuple[tuple[str, str], ...] | None = None
    ready_timeout_seconds: int | None = None
    request_timeout_seconds: int | None = None

    @property
    def server_files(self) -> tuple[ServerFile, ...]:
        """Every file the server reads, the model first."""
        if not self.files:
            return (ServerFile(self.model_file, self.model_sha256, MODEL_FLAG),)
        model = next(entry for entry in self.files if entry.flag == MODEL_FLAG)
        return (model, *(entry for entry in self.files if entry is not model))

    @property
    def ready_timeout(self) -> int:
        if self.ready_timeout_seconds is None:
            return DEFAULT_READY_SECONDS
        return self.ready_timeout_seconds

    @property
    def request_timeout(self) -> int:
        if self.request_timeout_seconds is None:
            return DEFAULT_REQUEST_TIMEOUT_SECONDS
        return self.request_timeout_seconds

    def to_dict(self) -> dict[str, Any]:
        document = {
            "engine": self.engine,
            "build": self.build,
            "model": {"file": self.model_file, "sha256": self.model_sha256},
            "arguments": list(self.arguments),
            "served_model": self.served_model,
        }
        if self.files:
            document["files"] = [entry.to_dict() for entry in self.files]
        if self.environment is not None:
            document["environment"] = dict(self.environment)
        if self.ready_timeout_seconds is not None:
            document["ready_timeout_seconds"] = self.ready_timeout_seconds
        if self.request_timeout_seconds is not None:
            document["request_timeout_seconds"] = self.request_timeout_seconds
        return document


def _flag_name(token: str) -> str:
    """The flag llama.cpp looks *token* up as: it rewrites ``_`` to ``-`` in every ``--``
    token (b12182 ``common/arg.cpp``), so ``--hf_repo`` is ``--hf-repo``."""
    name = token.split("=", 1)[0]
    return name.replace("_", "-") if name.startswith("--") else name


def _refused_flag(token: str) -> bool:
    return _flag_name(token) in REFUSED_FLAGS


def environment_refusal(environment, *, host: bool = False) -> str | None:
    """Why *environment* cannot be given to the server, or None when it can; the host config
    may also set :data:`HOST_ONLY_ENVIRONMENT`."""
    if not isinstance(environment, dict):
        return "invalid"
    for name, value in environment.items():
        if (
            not isinstance(name, str)
            or not _ENVIRONMENT_NAME.fullmatch(name)
            or not isinstance(value, str)
            or "\0" in value
        ):
            return "invalid"
        if host and name in HOST_ONLY_ENVIRONMENT:
            continue
        if (
            name in REFUSED_ENVIRONMENT
            or name.startswith(REFUSED_ENVIRONMENT_PREFIXES)
            or name.upper() in REFUSED_ENVIRONMENT_ANY_CASE
            or REFUSED_ENVIRONMENT_PATTERN.fullmatch(name)
        ):
            return "refused:" + name
    return None


def _setpriv() -> str:
    """``setpriv`` from the runner's PATH, before the server's own environment exists."""
    found = shutil.which("setpriv")
    if found is None:
        raise KarnError("model_server_setpriv_unavailable")
    return found


def _timeout(document: dict, key: str) -> int | None:
    if key not in document:
        return None
    value = document[key]
    if type(value) is not int or not 0 < value <= MAX_TIMEOUT_SECONDS:
        raise KarnError("model_server_timeout_invalid:" + key)
    return value


def _legacy_model(model) -> ServerFile:
    if (
        not isinstance(model, dict)
        or set(model) != {"file", "sha256"}
        or not isinstance(model["file"], str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}\.gguf", model["file"])
        # Only the named file is verified, so a split model's other parts would load unchecked.
        or re.search(r"-[0-9]{5}-of-[0-9]{5}\.gguf$", model["file"])
        or not isinstance(model["sha256"], str)
        or not _SHA256.fullmatch(model["sha256"])
    ):
        raise KarnError("model_server_model_invalid")
    return ServerFile(model["file"], model["sha256"], MODEL_FLAG)


def _declared_files(files) -> tuple[ServerFile, ...]:
    if not isinstance(files, list) or not files:
        raise KarnError("model_server_files_invalid")
    entries = []
    for entry in files:
        if (
            not isinstance(entry, dict)
            or not {"file", "sha256"} <= set(entry) <= {"file", "sha256", "flag"}
            or not isinstance(entry["file"], str)
            or not _FILE_NAME.fullmatch(entry["file"])
            or not isinstance(entry["sha256"], str)
            or not _SHA256.fullmatch(entry["sha256"])
        ):
            raise KarnError("model_server_files_invalid")
        flag = entry.get("flag")
        if flag is not None and (
            not isinstance(flag, str)
            or not re.fullmatch(r"--?[A-Za-z0-9][A-Za-z0-9-]{0,63}", flag)
            or flag == "-m"
            or _refused_flag(flag)
        ):
            raise KarnError("model_server_file_flag_not_allowed:" + str(flag)[:64])
        entries.append(ServerFile(entry["file"], entry["sha256"], flag))
    names = [entry.file for entry in entries]
    if len(set(names)) != len(names):
        raise KarnError("model_server_files_invalid")
    if sum(entry.flag == MODEL_FLAG for entry in entries) != 1:
        raise KarnError("model_server_files_need_one_model")
    # llama.cpp loads a split model's other parts by name, so every part must be declared.
    for name in names:
        shard = _SHARD.fullmatch(name)
        if shard:
            stem, total = shard.group(1), int(shard.group(3))
            parts = {f"{stem}-{n:05d}-of-{total:05d}.gguf" for n in range(1, total + 1)}
            if not parts <= set(names):
                raise KarnError("model_server_split_model_incomplete:" + stem[:64])
    return tuple(entries)


def model_server_spec(runtime: dict) -> ModelServerSpec | None:
    """The definition's model server, or None; a malformed one refuses the candidate."""
    environment = runtime["environment"]
    if MODEL_SERVER_ENV not in environment:
        return None
    try:
        document = json.loads(environment[MODEL_SERVER_ENV])
    except ValueError:
        raise KarnError("model_server_spec_invalid") from None
    optional = {"environment", "ready_timeout_seconds", "request_timeout_seconds"}
    if (
        not isinstance(document, dict)
        or not {"engine", "build", "arguments"} <= set(document)
        or set(document) - {"engine", "build", "arguments", "model", "files", *optional}
        or ("model" in document) == ("files" in document)
    ):
        raise KarnError("model_server_spec_invalid")
    arguments = document["arguments"]
    if document["engine"] != "llama.cpp":
        raise KarnError("model_server_engine_unsupported")
    if not isinstance(document["build"], str) or not _BUILD.fullmatch(document["build"]):
        raise KarnError("model_server_build_invalid")
    if "files" in document:
        files = _declared_files(document["files"])
        model = next(entry for entry in files if entry.flag == MODEL_FLAG)
    else:
        files, model = (), _legacy_model(document["model"])
    if not isinstance(arguments, list) or not all(isinstance(a, str) for a in arguments):
        raise KarnError("model_server_arguments_invalid")
    if any("\0" in argument for argument in arguments):
        raise KarnError("model_server_arguments_invalid")
    for token in arguments:
        if _refused_flag(token) or _flag_name(token) in FILE_FLAGS:
            raise KarnError("model_server_flag_not_allowed:" + _flag_name(token)[:64])
    server_environment = None
    if "environment" in document:
        refusal = environment_refusal(document["environment"])
        if refusal is not None:
            raise KarnError("model_server_environment_" + refusal[:96])
        server_environment = tuple(sorted(document["environment"].items()))
    ready = _timeout(document, "ready_timeout_seconds")
    request = _timeout(document, "request_timeout_seconds")
    served = environment.get("CONSTRUCT_MODEL", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", served):
        raise KarnError("model_server_requires_construct_model")
    if runtime["network"]["mode"] != "restricted":
        raise KarnError("model_server_requires_restricted_network")
    return ModelServerSpec(
        "llama.cpp",
        document["build"],
        model.file,
        model.sha256,
        tuple(arguments),
        served,
        files,
        server_environment,
        ready,
        request,
    )


@dataclass(frozen=True)
class ModelServerHost:
    """Where this host keeps llama.cpp builds and model files (host config ``[model_server]``)."""

    models_dir: Path | None = None
    llama_cpp: dict[str, Path] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    """``[model_server] environment``: variables only this host's builds need."""
    gpu_slots: tuple[str, ...] | None = None
    """``[model_server] gpu_slots``; None for the host's one unpinned GPU Slot."""


class ModelServerBusyError(KarnError):
    """Every GPU Slot of the host is locked, unusable, or has another job on its GPUs.

    ``unusable`` names the slots whose lock file could not be opened, and why."""

    def __init__(self, unusable: tuple[str, ...] = (), reason: str | None = None):
        super().__init__(reason or "model_server_busy")
        self.unusable = unusable

    def explained(self) -> str:
        """The refusal and every unusable slot behind it, for an operator to read."""
        return "; ".join((str(self), *self.unusable))


@dataclass(frozen=True)
class GpuReading:
    """What ``nvidia-smi`` reports of this host's GPUs, or why it reported nothing."""

    gpus: tuple[dict[str, Any], ...] | None
    compute_uuids: frozenset[str] = frozenset()
    reason: str | None = None


_GPU_INDEX = re.compile(r"0|[1-9][0-9]*")


_GPU_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def _gpu_number(text: str):
    """A reported number in plain ASCII digits, None for a bracketed ``[N/A]``; anything else
    makes the reading unreadable."""
    if text.startswith("[") and text.endswith("]"):
        return None
    if not _GPU_NUMBER.fullmatch(text):
        raise ValueError("nvidia_smi_unreadable")
    number = float(text)
    return int(number) if number.is_integer() else number


# One nvidia-smi in flight per process: one the kernel will not let die (D state) is kept here
# and no other starts until it is gone, so a stuck driver leaks one process, not one per read.
_NVIDIA_SMI = threading.Lock()
_abandoned: list[subprocess.Popen] = []


def _bounded(argv: list[str]) -> tuple[int, bytes]:
    """Run *argv* for at most :data:`NVIDIA_SMI_SECONDS`, never waiting on a process that
    will not die: an ``nvidia-smi`` stuck in the kernel is abandoned, not reaped, and while it
    lives, or another read is in flight, no other starts (``OSError``)."""
    if not _NVIDIA_SMI.acquire(blocking=False):
        raise OSError("nvidia_smi_in_flight")
    try:
        _abandoned[:] = [process for process in _abandoned if process.poll() is None]
        if _abandoned:
            raise OSError("nvidia_smi_in_flight")
        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        try:
            output, _ = process.communicate(timeout=NVIDIA_SMI_SECONDS)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):
                process.kill()
            with contextlib.suppress(OSError):
                process.stdout.close()
            _abandoned.append(process)
            raise
        return process.returncode, output
    finally:
        _NVIDIA_SMI.release()


def _nvidia_smi(query: list[str], run) -> list[list[str]]:
    code, output = run(["nvidia-smi", *query, "--format=csv,noheader,nounits"])
    if code:
        raise ValueError("nvidia_smi_failed")
    try:
        text = output.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("nvidia_smi_unreadable") from None
    return [
        [field.strip() for field in line.split(",")] for line in text.splitlines() if line.strip()
    ]


def read_gpus(run=None) -> GpuReading:
    """Every GPU's facts and the GPUs running a compute process; nothing, with a reason, when
    ``nvidia-smi`` is missing, fails, hangs or says something unreadable."""
    run = run or _bounded
    try:
        rows = _nvidia_smi(["--query-gpu=" + GPU_QUERY], run)
        apps = _nvidia_smi(["--query-compute-apps=gpu_uuid,pid,used_memory"], run)
        gpus = []
        for row in rows:
            if len(row) != 7 or not _GPU_INDEX.fullmatch(row[0]):
                raise ValueError("nvidia_smi_unreadable")
            index, uuid_, name, used, total, power, driver = row
            gpus.append(
                {
                    "index": int(index),
                    "uuid": uuid_,
                    "name": name,
                    "memory_total_mib": _gpu_number(total),
                    "memory_used_mib": _gpu_number(used),
                    "power_limit_w": _gpu_number(power),
                    "driver_version": driver,
                }
            )
    except (OSError, subprocess.TimeoutExpired):
        return GpuReading(None, reason="nvidia_smi_unavailable")
    except ValueError as error:
        return GpuReading(None, reason=str(error))
    return GpuReading(tuple(gpus), frozenset(row[0] for row in apps if row[0]))


@dataclass(frozen=True)
class GpuSlot:
    """One GPU Slot: a ``CUDA_VISIBLE_DEVICES`` value and its lock, or, with no ``gpu_slots``,
    the host-wide lock on the GPUs the runner's own selection gives the server."""

    value: str | None
    lock_path: Path

    @property
    def indices(self) -> frozenset[int] | None:
        return None if self.value is None else frozenset(map(int, self.value.split(",")))

    def gpus(self, reading: GpuReading) -> list[dict[str, Any]] | None:
        """The slot's GPUs; without ``gpu_slots``, every GPU ``nvidia-smi`` lists, which the
        runner's recorded selection narrows."""
        if reading.gpus is None:
            return None
        if self.indices is None:
            return list(reading.gpus)
        return [gpu for gpu in reading.gpus if gpu["index"] in self.indices]

    def busy(self, reading: GpuReading) -> str | None:
        """Why another job keeps this GPU Slot busy, whatever its lock says; None when nothing
        does. Only a listed GPU Slot is checked: without ``gpu_slots`` a host's own display
        may hold GPU memory, and only the lock decides, as it does without a reading."""
        if self.value is None:
            return None
        for gpu in self.gpus(reading) or ():
            if gpu["uuid"] in reading.compute_uuids:
                return "compute_process"
            used = gpu["memory_used_mib"]
            if isinstance(used, (int, float)) and used > BUSY_MEMORY_MIB:
                return "memory_used"
        return None

    def unknown_gpus(self, reading: GpuReading) -> bool:
        """Whether the slot names a GPU a readable ``nvidia-smi`` does not list."""
        if self.indices is None or reading.gpus is None:
            return False
        return not self.indices <= {gpu["index"] for gpu in reading.gpus}


def gpu_slots(state_root: Path, configured: tuple[str, ...] | None) -> tuple[GpuSlot, ...]:
    """The host's GPU Slots in config order; a lock is named by its slot's value, so reordering
    the list never moves a held lock onto another GPU."""
    root = Path(state_root).resolve()
    if configured is None:
        return (GpuSlot(None, root / "model-server.lock"),)
    return tuple(GpuSlot(value, root / f"model-server-gpu-{value}.lock") for value in configured)


def gpu_environment(slot_value: str | None, inherited=None) -> dict[str, str]:
    """The server's GPU selection: a GPU Slot's GPUs in ``nvidia-smi``'s order, or, without
    ``gpu_slots``, the runner's own ``CUDA_VISIBLE_DEVICES`` and ``CUDA_DEVICE_ORDER`` exactly
    as set, empty or absent."""
    if slot_value is not None:
        return {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": slot_value}
    inherited = os.environ if inherited is None else inherited
    return {name: inherited[name] for name in GPU_SELECTION if name in inherited}


# Locks kept for this process's lifetime: a server that outlived its stop may still be on the
# GPUs, and dropping the last reference to a handle would release its flock.
_kept_locks: list = []


class GpuSlotClaim:
    """A held GPU Slot, the GPU selection its server gets, and what ``nvidia-smi`` said of its
    GPUs when it was claimed.

    Once a server is linked, every release checks it: the slot is released only once the
    server is confirmed stopped, else kept until this process exits."""

    def __init__(self, slot: GpuSlot, handle, reading: GpuReading, inherited=None):
        self.slot, self._handle = slot, handle
        self.gpus = slot.gpus(reading)
        self.gpus_reason = reading.reason
        self.environment = gpu_environment(slot.value, inherited)
        self._server = None

    def link(self, server) -> None:
        """Tie the claim to the server it holds the GPUs for (anything with ``stopped``)."""
        self._server = server

    def release(self) -> None:
        if self._handle is None:
            return
        if self._server is not None and not self._server.stopped:
            self.keep_until_exit()
            return
        self._handle.close()
        self._handle = None

    def keep_until_exit(self) -> None:
        """Hold the lock until this process exits: its server may still be on the GPUs."""
        if self._handle is not None:
            _kept_locks.append(self._handle)
            self._handle = None

    def facts(self) -> dict[str, Any]:
        facts: dict[str, Any] = {
            "gpu_slot": self.slot.value,
            "cuda_visible_devices": self.environment.get("CUDA_VISIBLE_DEVICES"),
            "cuda_device_order": self.environment.get("CUDA_DEVICE_ORDER"),
            "gpus": self.gpus,
        }
        if self.gpus is None:
            facts["gpus_reason"] = self.gpus_reason
        return facts


def _lock(slot: GpuSlot):
    """The slot's lock, held; None when another process holds it. Raises ``OSError`` when the
    lock file cannot be created or opened."""
    slot.lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = slot.lock_path.open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    except BaseException:
        handle.close()
        raise
    return handle


def _needs_reading(slots: tuple[GpuSlot, ...]) -> bool:
    return any(slot.value is not None for slot in slots)


def _unknown(slot: GpuSlot) -> str:
    return f"gpu_slot_unknown_gpu:{slot.value}: nvidia-smi lists no such GPU"


def _lock_unusable(path: Path, reason: str) -> str:
    return f"model_server_lock_unusable: {path}: {reason}"


def claim_gpu_slot(slots: tuple[GpuSlot, ...], read=None, inherited=None) -> GpuSlotClaim:
    """The first free GPU Slot, held until released; ``model_server_busy`` when none is.

    A slot naming a GPU ``nvidia-smi`` does not list, or whose lock file cannot be opened, is
    unusable and skipped, never the end of the run; with no slot usable at all the error is
    ``gpu_slot_unknown_gpu:<values>`` when unknown GPUs are why. Either way it defers."""
    reading = (read or read_gpus)()
    unusable, unknown = [], []
    for slot in slots:
        if slot.unknown_gpus(reading):
            unusable.append(_unknown(slot))
            unknown.append(slot.value)
            continue
        if slot.busy(reading) is not None:
            continue
        try:
            handle = _lock(slot)
        except OSError as error:
            unusable.append(_lock_unusable(slot.lock_path, error.strerror or type(error).__name__))
            continue
        if handle is not None:
            return GpuSlotClaim(slot, handle, reading, inherited)
    raise ModelServerBusyError(
        tuple(unusable),
        "gpu_slot_unknown_gpu:" + ",".join(unknown)
        if len(unusable) == len(slots) and unknown
        else None,
    )


def gpu_slot_availability(
    slots: tuple[GpuSlot, ...], read=None, locks: Path | None = None
) -> tuple[bool, tuple[str, ...]]:
    """Whether some GPU Slot looks claimable, and the slots whose lock file is unusable.

    An admission hint for the scheduler, read like the monitor reads it: from the kernel's lock
    table, never by taking a lock a run is about to claim. The claim stays authoritative."""
    from silverquillm.monitor.locks import PROC_LOCKS, held_locks, lock_held

    reading = (read or read_gpus)() if _needs_reading(slots) else GpuReading(None)
    held = held_locks(locks or PROC_LOCKS)
    claimable, unusable = False, []
    for slot in slots:
        if slot.unknown_gpus(reading):
            unusable.append(_unknown(slot))
        elif _unusable(slot.lock_path):
            unusable.append(_lock_unusable(slot.lock_path, "Permission denied"))
        elif (
            slot.busy(reading) is None
            and lock_held(slot.lock_path, held, follow_symlinks=True) is not True
        ):
            claimable = True
    return claimable, tuple(unusable)


def _unusable(path: Path) -> bool:
    """A lock file this process could not open for a claim, or could not create."""
    if path.exists():
        return not os.access(path, os.R_OK | os.W_OK)
    return path.parent.exists() and not os.access(path.parent, os.W_OK)


@dataclass(frozen=True)
class ModelServerPlan:
    """A spec resolved against this host before any evidence exists."""

    spec: ModelServerSpec
    binary: Path
    version: str
    commit: str
    model_path: Path
    state_root: Path
    files: tuple[tuple[ServerFile, Path], ...] = ()
    host_environment: dict[str, str] = field(default_factory=dict)
    gpu_slots: tuple[str, ...] | None = None
    binary_sha256: str | None = None
    claim: GpuSlotClaim | None = None
    """The GPU Slot the run holds, from its claim until its server stops."""

    @property
    def server_files(self) -> tuple[tuple[ServerFile, Path], ...]:
        """Every file the server reads with its resolved path, the model first."""
        return self.files or ((self.spec.server_files[0], self.model_path),)

    def to_dict(self) -> dict[str, Any]:
        facts = {
            **self.spec.to_dict(),
            "binary": str(self.binary),
            "binary_version": self.version,
            "binary_commit": self.commit,
            "model_path": str(self.model_path),
            "host": {
                "environment": dict(self.host_environment),
                "binary_sha256": self.binary_sha256,
                **(self.claim.facts() if self.claim is not None else {}),
            },
        }
        if self.spec.files:
            facts["file_paths"] = {entry.file: str(path) for entry, path in self.server_files}
        return facts


def claim_model_server(plan: ModelServerPlan, read=None, inherited=None) -> ModelServerPlan:
    """The plan holding the host's first free GPU Slot; ``model_server_busy`` when none is.

    The GPU selection is fixed at the claim, so the server gets the selection the run records
    before launch, whatever the runner's environment says later."""
    slots = gpu_slots(plan.state_root, plan.gpu_slots)
    return replace(plan, claim=claim_gpu_slot(slots, read or read_gpus, inherited))


def server_environment(
    spec: ModelServerSpec,
    host_environment: dict[str, str],
    home: Path,
    inherited: dict[str, str] | None = None,
    *,
    gpu: dict[str, str] | None = None,
) -> dict[str, str]:
    """The whole environment of the server and of its ``--version`` probe: never the runner's,
    where a stray ``LD_LIBRARY_PATH`` or ``LLAMA_ARG_*`` would change the server unseen.

    *home* is an empty directory the bench owns, so llama.cpp reads no user config file;
    *gpu* is the claimed GPU selection (:func:`gpu_environment`); without one, as for the
    ``--version`` probe, the runner's own CUDA selection passes.
    """
    inherited = os.environ if inherited is None else inherited
    environment = {"PATH": inherited["PATH"]} if "PATH" in inherited else {}
    environment.update(host_environment)
    environment.update(spec.environment or ())
    environment.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"))
    environment.update(gpu_environment(None, inherited) if gpu is None else gpu)
    return environment


def plan_model_server(
    spec: ModelServerSpec,
    host: ModelServerHost,
    state_root: Path,
    claim: GpuSlotClaim | None = None,
):
    """Refuse a server this host cannot start: a missing build or file, or the wrong build.

    Given the run's *claim*, the ``--version`` probe runs on the claimed GPU selection, so on a
    host with GPU Slots it never touches another slot's GPUs."""
    refusal = environment_refusal(host.environment, host=True)
    if refusal is not None:
        raise KarnError("model_server_host_environment_" + refusal[:96])
    for config in SYSTEM_CONFIG_FILES:
        if os.path.lexists(config):
            raise KarnError("model_server_config_file_present:" + str(config))
    _setpriv()
    binary = host.llama_cpp.get(spec.build)
    if binary is None:
        raise KarnError("model_server_build_unavailable:" + spec.build)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise KarnError("model_server_binary_unavailable:" + spec.build)
    try:
        # The build verified is the build served: the same libraries, the same config.
        with tempfile.TemporaryDirectory(prefix="silverquillm-llama-home-") as home:
            result = subprocess.run(
                [str(binary), "--version"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=server_environment(
                    spec,
                    host.environment,
                    Path(home),
                    gpu=claim.environment if claim is not None else None,
                ),
            )
    except (OSError, subprocess.TimeoutExpired):
        raise KarnError("model_server_binary_unavailable:" + spec.build) from None
    found = _VERSION.search(result.stdout + result.stderr)
    if found is None or found.group(1) != _BUILD.fullmatch(spec.build).group(1):
        raise KarnError("model_server_build_mismatch:" + spec.build)
    if host.models_dir is None:
        raise KarnError("model_server_models_dir_unset")
    models_dir = host.models_dir.resolve()
    files = []
    for entry in spec.server_files:
        # The server gets the declared name, so llama.cpp derives a split model's other parts
        # from declared names only, never from a link's target.
        path = models_dir / entry.file
        target = path.resolve()
        if models_dir not in target.parents or not target.is_file():
            raise KarnError("model_file_unavailable:" + entry.file)
        files.append((entry, path))
    return ModelServerPlan(
        spec,
        binary.resolve(),
        found.group(0),
        found.group(2),
        files[0][1],
        Path(state_root).resolve(),
        tuple(files),
        dict(host.environment),
        host.gpu_slots,
        _sha256(binary.resolve()),
        claim,
    )


def file_sha256(path: Path) -> str:
    """A declared file's digest, verified during the run."""
    return _sha256(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class LlamaServer:
    """One loopback ``llama-server`` for one run, stopped with it."""

    def __init__(
        self, plan: ModelServerPlan, log_path: Path, *, ready_seconds: float | None = None
    ):
        self.plan, self.log_path = plan, log_path
        self.ready_seconds = plan.spec.ready_timeout if ready_seconds is None else ready_seconds
        self.process: subprocess.Popen | None = None
        self.port: int | None = None

    def command(self, port: int) -> list[str]:
        spec = self.plan.spec
        return [
            # The parent-death signal: a runner killed outright must not leave the GPUs held.
            _setpriv(),
            "--pdeathsig",
            "TERM",
            "--",
            str(self.plan.binary),
            "--model",
            str(self.plan.model_path),
            *(
                argument
                for entry, path in self.plan.server_files[1:]
                if entry.flag is not None
                for argument in (entry.flag, str(path))
            ),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--alias",
            spec.served_model,
            "--no-webui",
            *spec.arguments,
        ]

    def __enter__(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        home = self.log_path.parent / "model-server-home"
        home.mkdir(exist_ok=True)
        log = self.log_path.open("ab")
        try:
            self.process = subprocess.Popen(
                self.command(self.port),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=server_environment(
                    self.plan.spec,
                    self.plan.host_environment,
                    home,
                    gpu=self.plan.claim.environment if self.plan.claim is not None else None,
                ),
            )
        finally:
            log.close()
        try:
            self._wait_ready()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _wait_ready(self):
        deadline = time.monotonic() + self.ready_seconds
        while True:
            if self.process.poll() is not None:
                raise KarnError("model_server_exited_before_ready")
            with contextlib.suppress(OSError, http.client.HTTPException):
                connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
                try:
                    connection.request("GET", "/health")
                    if connection.getresponse().status == 200:
                        return
                finally:
                    connection.close()
            if time.monotonic() >= deadline:
                raise KarnError("model_server_not_ready")
            time.sleep(1)

    @property
    def stopped(self) -> bool:
        """Whether the server process is confirmed gone, so its GPUs are free."""
        return self.process is None or self.process.poll() is not None

    def __exit__(self, *_):
        if self.stopped:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=30)


def _usage(usage: Any) -> dict[str, int | None] | None:
    """Chat-completions usage in the record's token keys. llama.cpp bills no cache writes and
    does not split reasoning tokens out of ``completion_tokens``."""
    if not isinstance(usage, dict):
        return None
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}

    def count(value):
        return (
            value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        )

    return {
        "input_tokens": count(usage.get("prompt_tokens")),
        "cached_input_tokens": count(prompt_details.get("cached_tokens")),
        "cache_write_input_tokens": 0,
        "output_tokens": count(usage.get("completion_tokens")),
        "reasoning_output_tokens": count(completion_details.get("reasoning_tokens")),
        "total_tokens": count(usage.get("total_tokens")),
    }


class _Response:
    """What one completion said, assembled from a stream or read whole."""

    def __init__(self):
        self.response_id = self.model = self.finish_reason = None
        self.usage = self.timings = None
        self.usage_reports = 0
        self.content: list[str] = []
        self.reasoning: list[str] = []
        self.tool_calls: dict[int, dict[str, Any]] = {}
        self.stream_done = self._streamed = False
        self._pending = b""

    @property
    def complete(self) -> bool:
        """The server finished the completion: a final choice and, for a stream, its end
        marker. An upstream that closes early can still end the HTTP response cleanly."""
        return self.finish_reason is not None and (self.stream_done or not self._streamed)

    def feed_stream(self, chunk: bytes) -> None:
        self._streamed = True
        lines = (self._pending + chunk).split(b"\n")
        self._pending = lines.pop()
        for line in lines:
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                self.stream_done = True
                continue
            with contextlib.suppress(ValueError, RecursionError):
                self.ingest(json.loads(payload), delta=True)

    def ingest(self, document: Any, *, delta: bool) -> None:
        if not isinstance(document, dict):
            return
        self.response_id = document.get("id") or self.response_id
        self.model = document.get("model") or self.model
        if document.get("usage") is not None:
            self.usage = document["usage"]
            self.usage_reports += 1
        if isinstance(document.get("timings"), dict):
            self.timings = document["timings"]
        for choice in document.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            self.finish_reason = choice.get("finish_reason") or self.finish_reason
            message = choice.get("delta" if delta else "message") or {}
            if not isinstance(message, dict):
                continue
            if isinstance(message.get("content"), str):
                self.content.append(message["content"])
            if isinstance(message.get("reasoning_content"), str):
                self.reasoning.append(message["reasoning_content"])
            for position, call in enumerate(message.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                index = call.get("index", position) if delta else position
                row = self.tool_calls.setdefault(index, {"id": None, "name": "", "arguments": ""})
                row["id"] = call.get("id") or row["id"]
                function = call.get("function") or {}
                row["name"] += function.get("name") or ""
                row["arguments"] += function.get("arguments") or ""

    def message(self) -> dict[str, Any]:
        return {
            "content": "".join(self.content),
            "reasoning": "".join(self.reasoning),
            "tool_calls": [self.tool_calls[key] for key in sorted(self.tool_calls)],
        }


def _kept(value: Any, limit: int) -> Any:
    """Workload-controlled content as kept in the run's files: whole, or cut to ``limit``."""
    text = json.dumps(value, sort_keys=True, default=str)
    if len(text) <= limit:
        return value
    return {"truncated_from_chars": len(text), "head": text[:limit]}


def _new_messages(request: dict) -> Any:
    """The messages after the last assistant turn: what the agent added since its last reply."""
    messages = request.get("messages")
    if not isinstance(messages, list):
        return []
    added = messages
    for position in range(len(messages) - 1, -1, -1):
        if isinstance(messages[position], dict) and messages[position].get("role") == "assistant":
            added = messages[position + 1 :]
            break
    return _kept(added, MAX_KEPT_MESSAGES_CHARS)


class _EventFile:
    """A JSON-lines file whose committed prefix is whole lines: a failed append is cut back
    before the next one, so recovery never reads a row a live summary did not count."""

    def __init__(self, path: Path):
        self.fd: int | None = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        self.committed = 0
        self.broken = False

    def append(self, row: dict[str, Any]) -> bool:
        if self.fd is None or self.broken:
            return False
        try:
            line = memoryview((json.dumps(row, sort_keys=True) + "\n").encode())
        except (TypeError, ValueError):
            return False
        size = len(line)
        try:
            while line:
                line = line[os.write(self.fd, line) :]
        except OSError:
            try:
                os.ftruncate(self.fd, self.committed)
                os.lseek(self.fd, self.committed, os.SEEK_SET)
            except OSError:
                self.broken = True
            return False
        self.committed += size
        return True

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class ModelRelayCollector:
    """Starts the server on the plan's GPU Slot, relays and records requests, and releases the
    GPU Slot once the server has stopped.

    The relay listens on ``bind_host`` under a secret path, which only the run's proxy
    sidecar is given; the server itself listens on loopback only.
    """

    adapter = TELEMETRY_ADAPTER

    def __init__(self, run_dir: Path, *, plan: ModelServerPlan, bind_host: str = "127.0.0.1"):
        self.run_dir, self.plan, self.bind_host = Path(run_dir), plan, bind_host
        self.path = "/model/" + secrets.token_hex(16)
        self.events: list[dict[str, Any]] = []
        self.reasons: list[str] = []
        self.facts: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._exit = contextlib.ExitStack()
        self._server = self._thread = None
        self._sink = self._transcript = None
        self.llama: LlamaServer | None = None
        # Requests between admission and their terminal record, by relay id, with the sockets
        # that cancelling one shuts down.
        self._active: dict[str, list[socket.socket]] = {}
        self._cancelled: set[str] = set()
        self._idle = threading.Condition(self._lock)
        self._closing = self._settled = False

    def __enter__(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.plan.claim is not None:
            self._exit.callback(self.plan.claim.release)
        try:
            started = time.monotonic()
            for position, (entry, path) in enumerate(self.plan.server_files):
                if file_sha256(path) != entry.sha256:
                    raise KarnError(
                        "model_digest_mismatch"
                        if position == 0
                        else "model_file_digest_mismatch:" + entry.file
                    )
            # ``model_sha256_verified`` covers every declared file, the model among them.
            self.facts = {
                **self.plan.to_dict(),
                "model_sha256_verified": True,
                "model_bytes": self.plan.model_path.stat().st_size,
                "verify_seconds": round(time.monotonic() - started, 3),
            }
            if self.plan.spec.files:
                self.facts["file_bytes"] = {
                    entry.file: path.stat().st_size for entry, path in self.plan.server_files
                }
            self._sink = self._open(EVENTS_FILE)
            self._transcript = self._open(TRANSCRIPT_FILE)
            started = time.monotonic()
            # Known before it starts, so a server that fails to stop keeps its GPU Slot held.
            self.llama = LlamaServer(self.plan, self.run_dir / SERVER_LOG)
            if self.plan.claim is not None:
                self.plan.claim.link(self.llama)
            self._exit.enter_context(self.llama)
            self.facts["ready_seconds"] = round(time.monotonic() - started, 3)
            self._start_relay()
        except BaseException:
            self._exit.close()
            raise
        return self

    def _open(self, name: str) -> _EventFile:
        sink = _EventFile(self.run_dir / name)
        self._exit.callback(sink.close)
        return sink

    @property
    def endpoint(self) -> str:
        if self._server is None:
            raise RuntimeError("relay_not_started")
        return f"http://{self.bind_host}:{self._server.server_port}{self.path}"

    def mark_incomplete(self, reason: str) -> None:
        with self._lock:
            self.reasons.append(reason)

    def harvest_native(self, native_state: Path) -> None:
        """A model-server run has no native journals; the relay saw every request."""

    def _commit(self, event: dict[str, Any]) -> bool:
        """An event counts only once it is in the file, so live and recovered summaries of
        the run agree."""
        with self._lock:
            if self._sink is None or not self._sink.append(event):
                return False
            self.events.append(event)
            return True

    def record(self, event: dict[str, Any], transcript: dict[str, Any] | None) -> bool:
        with self._lock:
            if self._settled:
                # The summary is computed; a late record would make the event file disagree.
                return False
            if not self._commit(event):
                return False
            if transcript is not None and not (
                self._transcript is not None and self._transcript.append(transcript)
            ):
                # The terminal event stands; the transcript is only short of this row.
                self._commit({"id": event["id"], "kind": TRANSCRIPT_LOST})
            return True

    def _start_relay(self):
        collector = self

        class Relay(BaseHTTPRequestHandler):
            # HTTP/1.0: each response ends when the relay closes, so a stream needs no framing.
            protocol_version = "HTTP/1.0"
            # Reading a request; the sidecar sends each one whole.
            timeout = 300

            def log_message(self, *args):
                pass

            def do_GET(self):
                collector.relay(self)

            def do_POST(self):
                collector.relay(self)

        self._server = ThreadingHTTPServer((self.bind_host, 0), Relay)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        # Runs before the sinks close and the server stops, so no handler writes to either.
        self._exit.callback(self._settle)

    def relay(self, handler: BaseHTTPRequestHandler) -> None:
        if not handler.path.startswith(self.path + "/"):
            handler.send_error(404)
            return
        target = handler.path[len(self.path) :]
        if (handler.command, target) not in RELAYED_PATHS:
            handler.send_error(404)
            return
        length = handler.headers.get("Content-Length") or "0"
        if not length.isdigit() or int(length) > MAX_REQUEST_BYTES:
            handler.send_error(413)
            return
        body = handler.rfile.read(int(length))
        if handler.command == "GET":
            self._forward(handler, target, body, None)
            return
        try:
            request = json.loads(body)
        except (ValueError, RecursionError):
            handler.send_error(400)
            return
        request = request if isinstance(request, dict) else {}
        # Several choices in one stream would each report usage; pi asks for one.
        if request.get("n", 1) != 1:
            handler.send_error(400)
            return
        self._forward(handler, target, body, request)

    def _admit(self, identity, client: socket.socket, request, started_ms) -> bool:
        """Registers a request, and durably records its start before the server sees it: a
        runner that dies mid-request still leaves the request counted, as unfinished. A start
        that cannot be written is refused, so the file and the summary never disagree."""
        with self._lock:
            if self._closing or self._sink is None or self._sink.broken:
                return False
            if request is not None:
                start = {
                    "id": identity,
                    "kind": REQUEST_STARTED,
                    "requested_model": _kept(request.get("model"), 256),
                    "stream": bool(request.get("stream")),
                    "timestamp_ms": started_ms,
                }
                if not self._commit(start):
                    return False
            self._active[identity] = [client]
            return True

    def _connected(self, identity, upstream: socket.socket) -> None:
        with self._lock:
            # Kept apart from the connection, which drops its socket once a response that
            # closes the connection begins.
            self._active[identity].append(upstream)
            if identity in self._cancelled:
                raise ConnectionAbortedError

    def _release(self, identity) -> None:
        with self._lock:
            self._active.pop(identity, None)
            self._idle.notify_all()

    def _cancel_active(self) -> None:
        with self._lock:
            for identity, sockets in self._active.items():
                self._cancelled.add(identity)
                for held in sockets:
                    # Wakes the handler's blocked read or write; llama-server drops the task.
                    with contextlib.suppress(OSError):
                        held.shutdown(socket.SHUT_RDWR)

    def _forward(self, handler, target: str, body: bytes, request: dict | None) -> None:
        started_ms = int(time.time() * 1000)
        # One event per relayed request, whatever ids the server reuses.
        identity = "relay-" + uuid.uuid4().hex
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.llama.port, timeout=self.plan.spec.request_timeout
        )
        if not self._admit(identity, handler.connection, request, started_ms):
            with contextlib.suppress(OSError):
                handler.send_error(503)
            return
        try:
            self._relay_upstream(handler, target, body, request, identity, connection, started_ms)
        finally:
            self._release(identity)

    def _relay_upstream(self, handler, target, body, request, identity, connection, started_ms):
        response, status, error = _Response(), None, None
        try:
            connection.connect()
            self._connected(identity, connection.sock)
            headers = {"Content-Type": "application/json"} if body else {}
            connection.request(handler.command, target, body or None, headers)
            upstream = connection.getresponse()
            status = upstream.status
            handler.send_response(status)
            kind = upstream.getheader("Content-Type", "application/json")
            handler.send_header("Content-Type", kind)
            handler.send_header("Cache-Control", "no-cache")
            handler.end_headers()
            streaming = kind.startswith("text/event-stream")
            whole = []
            while chunk := upstream.read1(65536):
                if streaming:
                    response.feed_stream(chunk)
                elif request is not None:
                    whole.append(chunk)
                try:
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
                except OSError:
                    error = "client_disconnected"
                    break
            if whole:
                with contextlib.suppress(ValueError, RecursionError):
                    response.ingest(json.loads(b"".join(whole)), delta=False)
            if upstream.length:
                error = error or "upstream_response_truncated"
            if request is not None and status == 200 and not error and not response.complete:
                error = "upstream_response_incomplete"
        except (OSError, http.client.HTTPException) as failure:
            error = error or "upstream_failed:" + type(failure).__name__
            if status is None:
                with contextlib.suppress(OSError):
                    handler.send_error(502)
        finally:
            connection.close()
        if identity in self._cancelled:
            # A cancelled stream can end like a finished one; it is never counted as complete.
            error = "cancelled_at_finalize"
        if request is None:
            return
        try:
            recorded = self._observe(identity, request, response, status, error, started_ms)
        except Exception:  # noqa: BLE001 -- a request the server saw is never left unrecorded.
            recorded = False
        if not recorded:
            # If this cannot be written either, the durable start leaves the request unfinished.
            self.record(
                {
                    "id": identity,
                    "kind": "response",
                    "response_id": identity,
                    "status": status,
                    "error": "observation_failed",
                    "usage": None,
                    "timestamp_ms": started_ms,
                },
                None,
            )

    def _observe(self, identity, request, response: _Response, status, error, started_ms):
        message = response.message()
        messages = request.get("messages")
        overrides = sorted(set(request) - ORDINARY_REQUEST_KEYS)
        event = {
            "id": identity,
            "kind": "response",
            "response_id": _kept(response.response_id, 256) or identity,
            "thread_id": THREAD_ID,
            "model": _kept(response.model, 256),
            "requested_model": _kept(request.get("model"), 256),
            "request_parameters": _kept(
                {key: request[key] for key in overrides}, MAX_KEPT_FIELD_CHARS
            ),
            "status": status,
            "error": error,
            "finish_reason": _kept(response.finish_reason, 64),
            "usage": _usage(response.usage),
            "usage_reports": response.usage_reports,
            "timings": _kept(response.timings, MAX_KEPT_FIELD_CHARS),
            "tool_calls": len(message["tool_calls"]),
            "stream": bool(request.get("stream")),
            "max_completion_tokens": _kept(request.get("max_completion_tokens"), 64),
            "request_messages": len(messages) if isinstance(messages, list) else None,
            "timestamp_ms": started_ms,
            "completed_ms": int(time.time() * 1000),
        }
        transcript = {
            "id": identity,
            "response_id": event["response_id"],
            "timestamp_ms": started_ms,
            "new_messages": _new_messages(request),
            "response": _kept(message, MAX_KEPT_MESSAGES_CHARS),
            "finish_reason": response.finish_reason,
            "status": status,
            "error": error,
        }
        return self.record(event, transcript)

    def _settle(self) -> None:
        """Stops admitting requests, cancels those in flight, and waits a bounded time for
        their terminal records; nothing is recorded after this returns."""
        with self._lock:
            if self._settled:
                return
            self._closing = True
        self._cancel_active()
        self._stop_relay()
        with self._lock:
            deadline = time.monotonic() + SETTLE_SECONDS
            while self._active and (remaining := deadline - time.monotonic()) > 0:
                self._idle.wait(remaining)
            self._settled = True

    def finalize(self, *, exit_kind: str, native_version: str | None = None) -> dict[str, Any]:
        self._settle()
        with self._lock:
            result = summarize_model_events(
                self.events, exit_kind=exit_kind, collection_reasons=self.reasons
            )
            fd = os.open(
                self.run_dir / "observations.json",
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(result, output, sort_keys=True, indent=2)
                output.write("\n")
            return result

    def _stop_relay(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5)
            self._server = None

    def __exit__(self, *_):
        self._exit.close()


def _sum(rows, key):
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    return sum(values) if values else 0


def server_timings(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Throughput over every completed request, from the server's own ``timings``."""
    timings = [row["timings"] for row in rows if isinstance(row.get("timings"), dict)]
    prompt_ms, generation_ms = _sum(timings, "prompt_ms"), _sum(timings, "predicted_ms")
    prompt, generated = _sum(timings, "prompt_n"), _sum(timings, "predicted_n")
    return {
        "requests_with_timings": len(timings),
        "prompt_tokens_processed": prompt,
        "prompt_cache_tokens": _sum(timings, "cache_n"),
        "generated_tokens": generated,
        "prompt_seconds": round(prompt_ms / 1000, 3),
        "generation_seconds": round(generation_ms / 1000, 3),
        "prompt_tokens_per_second": round(prompt * 1000 / prompt_ms, 3) if prompt_ms else None,
        "generation_tokens_per_second": (
            round(generated * 1000 / generation_ms, 3) if generation_ms else None
        ),
    }


def summarize_model_events(events, *, exit_kind: str, collection_reasons=()) -> dict[str, Any]:
    """Measurements from the relay's events.

    Every request reaches one server, so the relay cannot tell a second agent process from
    the main one: subagent use is unknown, never ``none``.
    """
    reasons = list(collection_reasons)
    unique: dict[str, dict[str, Any]] = {}
    starts: dict[str, dict[str, Any]] = {}
    transcript_lost: set[str] = set()
    for event in events:
        if not isinstance(event, dict) or not event.get("id"):
            continue
        if event.get("kind") == "response":
            unique.setdefault(event["id"], event)
        elif event.get("kind") == REQUEST_STARTED:
            starts.setdefault(event["id"], event)
        elif event.get("kind") == TRANSCRIPT_LOST:
            transcript_lost.add(event["id"])
    unfinished = [start for identity, start in starts.items() if identity not in unique]
    for start in unfinished:
        # Started and never settled: cut off at the deadline, or its runner died.
        unique[start["id"]] = {
            "id": start["id"],
            "kind": "response",
            "status": None,
            "error": "request_unfinished",
            "usage": None,
            "timestamp_ms": start.get("timestamp_ms"),
        }
    rows = sorted(unique.values(), key=lambda row: row.get("timestamp_ms") or 0)
    completed = [row for row in rows if row.get("status") == 200 and not row.get("error")]
    failed = len(rows) - len(completed)
    if failed:
        # The server may have done the work of a request whose usage never reached the relay.
        reasons.append("relayed_request_incomplete")
    if any((row.get("usage_reports") or 0) > 1 for row in completed):
        reasons.append("multiple_usage_reports")
    requests = []
    for row in completed:
        usage = row.get("usage")
        if usage is None:
            reasons.append("response_usage_missing")
            usage = dict.fromkeys(TOKEN_KEYS)
        requests.append(
            {
                "response_id": row["response_id"],
                "thread_id": THREAD_ID,
                "model": row.get("model"),
                "usage": usage,
                "timestamp_ms": row.get("timestamp_ms"),
                "compaction": False,
                "finish_reason": row.get("finish_reason"),
                "timings": row.get("timings"),
            }
        )
    if exit_kind != "completed":
        reasons.append("execution_did_not_complete")
    measurements = _measurements(
        requests,
        len(completed),
        sum(row.get("tool_calls") or 0 for row in completed),
        reasons,
        True,
        {
            "source": TELEMETRY_ADAPTER,
            "relayed_requests": len(rows),
            "failed_requests": failed,
            "unfinished_requests": len(unfinished),
            "transcript_rows_missing": len(transcript_lost),
            "requests_with_parameter_overrides": sum(
                1 for row in rows if row.get("request_parameters")
            ),
        },
        subagent_threads=None,
        subagents=None,
        subagents_reason="threads_not_observable",
        # The served name is an alias the recipe chose; no hosted model's price applies to it.
        prices={},
    )
    measurements["server_timings"] = server_timings(completed)
    return measurements
