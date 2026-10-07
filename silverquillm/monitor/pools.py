"""Login Pools on this host, read without creating, locking, or reading any stored login."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from silverquillm.karn.login import LOGIN_PLUGINS
from silverquillm.karn.login_pool import SLOT_NAME, logins_root, recorded_plugin
from silverquillm.karn.subscription_usage import PROVIDERS

from .locks import lock_held


@dataclass(frozen=True)
class ProfileStatus:
    plugin_id: str
    slot: str
    provider: str
    busy: bool | None
    """None when the lock table is unavailable."""
    pending: bool
    """An interrupted run's login journal awaits recovery."""

    @property
    def ref(self) -> str:
        """The Login Profile as run inputs and records name it."""
        return f"{self.plugin_id}/{self.slot}"


def _enrolled(pool: Path, plugin_id: str) -> list[str]:
    """``LoginPool.enrolled`` without ``LoginPool.of``, which creates the pool directory."""
    try:
        entries = sorted(os.scandir(pool), key=lambda entry: entry.name)
    except OSError:
        return []
    return [
        entry.name
        for entry in entries
        if SLOT_NAME.fullmatch(entry.name)
        and entry.is_dir(follow_symlinks=False)
        and (Path(entry.path) / "secret.json").is_file()
        and recorded_plugin(Path(entry.path)) == plugin_id
    ]


def login_profiles(state_root: Path | None, held) -> list[ProfileStatus]:
    """Every enrolled Login Profile of every login plugin's pool, by plugin then slot."""
    if state_root is None:
        return []
    root = logins_root(Path(state_root))
    profiles = []
    for plugin_id in sorted(LOGIN_PLUGINS):
        for slot in _enrolled(root / plugin_id, plugin_id):
            directory = root / plugin_id / slot
            profiles.append(
                ProfileStatus(
                    plugin_id,
                    slot,
                    PROVIDERS[plugin_id],
                    lock_held(directory / "runner.lock", held),
                    (directory / "active.json").exists(),
                )
            )
    return profiles
