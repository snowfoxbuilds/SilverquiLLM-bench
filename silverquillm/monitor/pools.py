"""Login Pools on this host, read without creating, locking, or reading any stored login."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.karn.login import LOGIN_PLUGINS
from silverquillm.karn.login_cooldown import cooldown_until
from silverquillm.karn.login_pool import enrolled_slots, logins_root
from silverquillm.karn.subscription_usage import PROVIDERS

from ._read import read_json
from .locks import lock_held

JOURNAL_LIMIT = 1024 * 1024


@dataclass(frozen=True)
class ProfileStatus:
    plugin_id: str
    slot: str
    provider: str
    busy: bool | None
    """None when the lock table is unavailable."""
    pending: bool
    """An interrupted run's login journal awaits recovery."""
    pending_run: str | None = None
    """The run the pending journal names, when it names one; that run owns the settlement."""
    cooldown_until: datetime | None = None
    """When the profile's Login Cooldown ends; None when no cooldown is in force."""

    @property
    def free(self) -> bool:
        """Untapped: a new run could take it now."""
        return self.busy is False and not self.pending and self.cooldown_until is None

    @property
    def ref(self) -> str:
        """The Login Profile as run inputs and records name it."""
        return f"{self.plugin_id}/{self.slot}"


def _journal_run(path: Path) -> str | None:
    """Only the run id from a pending login journal; its other fields are never kept."""
    journal = read_json(path, limit=JOURNAL_LIMIT)
    run_id = journal.get("run_id") if isinstance(journal, dict) else None
    return run_id if isinstance(run_id, str) and 0 < len(run_id) <= 64 else None


def login_profiles(
    state_root: Path | None, held, *, now: datetime | None = None
) -> list[ProfileStatus]:
    """Every enrolled Login Profile of every login plugin's pool, by plugin then slot."""
    if state_root is None:
        return []
    root = logins_root(Path(state_root))
    profiles = []
    for plugin_id in sorted(LOGIN_PLUGINS):
        for slot in enrolled_slots(root / plugin_id, plugin_id):
            directory = root / plugin_id / slot
            journal = directory / "active.json"
            pending = journal.exists()
            profiles.append(
                ProfileStatus(
                    plugin_id,
                    slot,
                    PROVIDERS[plugin_id],
                    lock_held(directory / "runner.lock", held),
                    pending,
                    _journal_run(journal) if pending else None,
                    cooldown_until(directory, now=now),
                )
            )
    return profiles
