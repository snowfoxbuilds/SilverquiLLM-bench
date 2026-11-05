"""Slot management by provider name: add, re-enroll and remove Login Pool slots.

Enrolling needs only a login plugin, never a candidate: the plugin is taken from the host's
plugin cache (``<state-root>/plugins``), where every run installs its verified artifact.
``silverquillm login`` and ``top``'s LOGINS keys both come through here.
"""

from __future__ import annotations

import contextlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .definition import KarnError, PluginArtifact, canonical, digest, read_regular, strict_json
from .login import LOGIN_PLUGINS, private_directory
from .login_pool import SLOT_NAME, LoginPool

AGENTS = {"codex": "karn-codex-login", "claude": "karn-claude-login"}
PROVIDER_OF = {plugin_id: agent for agent, plugin_id in AGENTS.items()}
_DIGEST = re.compile(r"[0-9a-f]{64}")


def plugin_cache(state_root: Path) -> Path:
    return Path(state_root).resolve() / "plugins"


def slot_name(text: str) -> str:
    """``3`` or ``slot-3`` both name ``slot-3``; any other valid slot name is kept."""
    text = text.strip()
    name = f"slot-{int(text)}" if re.fullmatch(r"[0-9]{1,9}", text) else text
    if not SLOT_NAME.fullmatch(name):
        raise KarnError("invalid_login_slot")
    return name


@dataclass(frozen=True)
class CachedPlugin:
    artifact: PluginArtifact
    executable: Path


_MANIFEST_SHAPE = {"id": str, "module": str, "version": str, "sdk_major": int, "hooks": list}


def _private(path: Path) -> bool:
    info = os.stat(path, follow_symlinks=False)
    return stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077


def _cached(entry: Path) -> CachedPlugin | None:
    """One cache entry, trusted as ``install_plugin`` made it: private to this user, and its
    manifest still digesting to the directory's name."""
    if not _DIGEST.fullmatch(entry.name) or not _private(entry):
        return None
    try:
        manifest = strict_json(read_regular(entry / "artifact.json", limit=1024 * 1024))
    except KarnError:
        return None
    if not isinstance(manifest, dict) or not all(
        isinstance(manifest.get(key), kind) for key, kind in _MANIFEST_SHAPE.items()
    ):
        return None
    artifact_digest = "sha256:" + entry.name
    if digest(canonical(manifest, ascii_only=True)) != artifact_digest:
        return None
    executable = entry / "bin" / "python"
    if manifest.get("id") not in LOGIN_PLUGINS or not executable.is_file():
        return None
    row = {"id": manifest["id"], "artifact": artifact_digest, "configuration": {}}
    return CachedPlugin(PluginArtifact(row, manifest, entry, (), None), executable)


def cached_login_plugin(
    state_root: Path, plugin_id: str, *, artifact: str | None = None
) -> CachedPlugin:
    """The installed login plugin to enroll with: ``artifact`` when named, else the newest."""
    found = []
    try:
        # The same check ``install_plugin`` makes of the cache it writes.
        entries = list(private_directory(plugin_cache(state_root)).iterdir())
    except (KarnError, OSError):
        entries = []
    for entry in entries:
        # One entry vanishing or unreadable mid-scan leaves the others usable.
        with contextlib.suppress(KarnError, OSError):
            cached = _cached(entry)
            if (
                cached is not None
                and cached.artifact.row["id"] == plugin_id
                and artifact in (None, cached.artifact.row["artifact"])
            ):
                found.append((os.stat(entry / "artifact.json").st_mtime, entry.name, cached))
    if not found:
        raise KarnError(
            ("login_plugin_artifact_not_cached:" if artifact else "login_plugin_not_cached:")
            + plugin_id
        )
    return max(found, key=lambda item: item[:2])[2]


def enroll_slot(state_root: Path, agent: str, slot: str | None = None) -> tuple[str, int]:
    """Sign in a new slot (``slot`` None) or an enrolled one again; returns its ref and status.

    A new slot whose sign-in fails is discarded. A slot holding an interrupted run's login
    is re-enrolled with that run's own plugin artifact, so its pending login settles first.
    """
    from .host import DockerHost

    plugin_id = AGENTS[agent]
    pool = LoginPool.of(state_root, plugin_id)
    if slot is not None and slot not in pool.enrolled():
        raise KarnError("login_slot_not_enrolled")
    profile = pool.named_slot(slot) if slot else pool.new_slot()
    try:
        pending = profile.pending() if slot else None
        cached = cached_login_plugin(
            state_root, plugin_id, artifact=pending.get("plugin_artifact") if pending else None
        )
        host = DockerHost(plugin_cache=plugin_cache(state_root))
        status = host.enroll_login(profile, cached.artifact, executable=cached.executable)
    finally:
        if not slot:
            # The enrollment's own error, if any, is the one to report.
            with contextlib.suppress(OSError, KarnError):
                pool.discard_unenrolled(profile)
    return pool.ref(profile), status


def slot_identity(state_root: Path, agent: str, slot: str) -> tuple[int, int]:
    """What a removal confirmation is for: this slot as it is now, not its name."""
    return LoginPool.of(state_root, AGENTS[agent]).identity(slot)


def remove_slot(
    state_root: Path, agent: str, slot: str, *, identity: tuple[int, int] | None = None
) -> str:
    pool = LoginPool.of(state_root, AGENTS[agent])
    pool.remove(slot, identity=identity)
    return f"{pool.plugin_id}/{slot}"
