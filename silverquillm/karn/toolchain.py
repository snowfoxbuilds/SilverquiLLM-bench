"""The bench's pinned test toolchain, mounted read-only into every candidate container.

Candidates stay generic: the bench supplies pytest instead of requiring a construct to bake
it (KARN-BENCHMARK-CONTRACT.md, Implementation-only runs). The wheels are vendored beside
this module and pinned by the hash-locked ``requirements.txt``.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import io
import os
import re
import shutil
import stat
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from .definition import KarnError, canonical, digest, tree_digest

TOOLCHAIN_SOURCE = Path(__file__).with_name("candidate_toolchain")
TOOLCHAIN_TARGET = "/run/silverquillm/test-toolchain"
MAX_WHEEL_BYTES = 16 * 1024 * 1024
MAX_UNPACKED_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 4096


class Wheel(NamedTuple):
    path: Path
    sha256: str
    data: bytes


@dataclass(frozen=True)
class CandidateToolchain:
    path: Path
    digest: str

    def to_dict(self) -> dict:
        return {"digest": self.digest, "target": TOOLCHAIN_TARGET}


def _refuse(detail: str):
    raise KarnError("test_toolchain_integrity_mismatch:" + detail)


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_pins(requirements: Path) -> dict[str, tuple[str, frozenset[str]]]:
    """Read ``name==version --hash=sha256:…`` pins as uv/pip-compile writes them."""
    logical, pins = "", {}
    for line in requirements.read_text().splitlines():
        line = line.split("#", 1)[0].rstrip()
        if line.endswith("\\"):
            logical += line[:-1] + " "
            continue
        logical += line
        words = logical.split()
        logical = ""
        if not words:
            continue
        name, separator, version = words[0].partition("==")
        hashes = frozenset(
            word.removeprefix("--hash=sha256:") for word in words[1:] if word.startswith("--hash=")
        )
        if not separator or not hashes or len(hashes) != len(words) - 1:
            _refuse("requirements")
        pins[_normalize(name)] = (version, hashes)
    return pins


def _read_wheel(path: Path) -> bytes:
    """Read a vendored wheel once, through a descriptor that follows no symlink.

    Unlike ``read_regular``, a hard link is accepted: a non-editable install such as
    ``uv --link-mode hardlink`` links package files to the installer's cache. Another name for
    the same inode cannot swap the content, since these exact bytes are hashed and unpacked.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_WHEEL_BYTES:
                raise KarnError("unsafe_artifact_file")
            data = stream.read(MAX_WHEEL_BYTES + 1)
    except OSError:
        raise KarnError("artifact_file_unavailable") from None
    if len(data) > MAX_WHEEL_BYTES:
        raise KarnError("artifact_file_too_large")
    return data


def locked_wheels(source: Path = TOOLCHAIN_SOURCE) -> list[Wheel]:
    """Return the vendored wheels, each matching exactly one pin, pure-Python and unaltered.

    Each wheel carries the bytes that were hashed, so unpacking never rereads the file.
    """
    pins = read_pins(source / "requirements.txt")
    wheels, seen = [], set()
    for wheel in sorted((source / "wheels").iterdir()):
        parts = wheel.name.removesuffix(".whl").split("-")
        if wheel.suffix != ".whl" or len(parts) != 5 or parts[2:] != ["py3", "none", "any"]:
            _refuse(wheel.name)
        name, version = _normalize(parts[0]), parts[1]
        if name in seen or pins.get(name, ("",))[0] != version:
            _refuse(wheel.name)
        data = _read_wheel(wheel)
        sha = hashlib.sha256(data).hexdigest()
        if sha not in pins[name][1]:
            _refuse(wheel.name)
        seen.add(name)
        wheels.append(Wheel(wheel, sha, data))
    if seen != set(pins):
        _refuse("missing:" + ",".join(sorted(set(pins) - seen)))
    return wheels


def _unpack(wheel: Wheel, site: Path, budget: list[int]) -> None:
    try:
        _extract(wheel, site, budget)
    except (
        FileExistsError,
        IsADirectoryError,
        NotADirectoryError,
        zipfile.BadZipFile,
        zlib.error,
        EOFError,
    ) as error:
        # A pinned wheel whose members clash or fail their CRC is refused, not a host crash.
        _refuse(f"{wheel.path.name}:{type(error).__name__}")


def _extract(wheel: Wheel, site: Path, budget: list[int]) -> None:
    name_of = wheel.path.name
    with zipfile.ZipFile(io.BytesIO(wheel.data)) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            _refuse(name_of)
        for member in members:
            name = member.filename
            kind = stat.S_IFMT(member.external_attr >> 16)
            relative = PurePosixPath(name)
            if (
                "\\" in name
                or relative.is_absolute()
                or any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
                or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                or relative.parts[0].endswith(".data")
            ):
                _refuse(name_of)
            destination = site.joinpath(*relative.parts)
            if member.is_dir():
                destination.mkdir(mode=0o755, parents=True, exist_ok=True)
                continue
            budget[0] -= member.file_size
            if budget[0] < 0:
                _refuse(name_of)
            destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with archive.open(member) as stream, open(destination, "xb") as output:
                shutil.copyfileobj(stream, output)
            destination.chmod(0o644)


def _verified(final: Path) -> bool:
    try:
        return (final / "tree-digest").read_text() == tree_digest(final / "site")
    except (OSError, KarnError):
        return False


@contextlib.contextmanager
def _exclusive(root: Path):
    with open(root / ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def prepare_toolchain(state_root: Path, source: Path = TOOLCHAIN_SOURCE) -> CandidateToolchain:
    """Verify the pinned wheels and unpack them once per toolchain digest under the state root."""
    wheels = locked_wheels(source)
    value = digest(canonical([[wheel.path.name, wheel.sha256] for wheel in wheels]))
    root = Path(state_root).resolve() / "toolchains"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    final = root / value.split(":", 1)[1]
    # Concurrent runs share one tree: check, rebuild and rename happen under one host lock,
    # so no run deletes a tree another run has just verified.
    with _exclusive(root):
        if final.exists() and not _verified(final):
            shutil.rmtree(final)
        if not final.exists():
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=root))
            try:
                site = staging / "site"
                site.mkdir(mode=0o755)
                budget = [MAX_UNPACKED_BYTES]
                for wheel in wheels:
                    _unpack(wheel, site, budget)
                for directory in [site, *(p for p in site.rglob("*") if p.is_dir())]:
                    directory.chmod(0o755)
                (staging / "tree-digest").write_text(tree_digest(site))
                os.rename(staging, final)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        if not _verified(final):
            _refuse("unpacked")
    return CandidateToolchain(final / "site", value)
