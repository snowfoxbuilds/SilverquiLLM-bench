"""Per-provider pools of subscription logins, each serving one run at a time.

A pool holds one enrolled login per slot under ``<state-root>/logins/<plugin-id>/<slot>``;
any construct with that login plugin may use any free slot, so the number of slots is the
number of concurrent runs on that provider. A credential is never copied between slots:
refresh tokens rotate on use, so a copy would invalidate its original.
"""

from __future__ import annotations

import contextlib
import fcntl
import itertools
import os
import re
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .definition import KarnError
from .login import LOGIN_PLUGINS, LoginInUseError, LoginProfile, private_directory

SLOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
DEFAULT_POLL_SECONDS = 5.0


def logins_root(state_root: Path) -> Path:
    return Path(state_root).resolve() / "logins"


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _announce(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


@dataclass(frozen=True)
class LoginPool:
    root: Path
    plugin_id: str

    @classmethod
    def of(cls, state_root: Path, plugin_id: str) -> LoginPool:
        if plugin_id not in LOGIN_PLUGINS:
            raise KarnError("invalid_login_pool")
        return cls(private_directory(logins_root(state_root) / plugin_id), plugin_id)

    def ref(self, profile: LoginProfile) -> str:
        """The name a run input and record carry, from which recovery finds the slot again."""
        return f"{self.plugin_id}/{profile.name}"

    def slot(self, name: str) -> LoginProfile:
        if not SLOT_NAME.fullmatch(name):
            raise KarnError("invalid_login_slot")
        return LoginProfile(self.root / name, name)

    def enrolled(self) -> list[str]:
        """Slots holding a stored login; an enrollment that never finished is not one."""
        names = []
        for entry in sorted(self.root.iterdir()):
            if (
                SLOT_NAME.fullmatch(entry.name)
                and entry.is_dir()
                and not entry.is_symlink()
                and (entry / "secret.json").is_file()
            ):
                names.append(entry.name)
        return names

    @contextlib.contextmanager
    def _creating(self):
        """Serialize creating slot directories, so an adoption never renames over a new one."""
        descriptor = os.open(
            self.root / ".pool.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)

    def new_slot(self) -> LoginProfile:
        """Claim the lowest unused ``slot-N``; mkdir is the claim, so two enrollments never share."""
        with self._creating():
            for number in itertools.count(1):
                name = f"slot-{number}"
                try:
                    os.mkdir(self.root / name, 0o700)
                except FileExistsError:
                    continue
                return self.slot(name)
        raise AssertionError("unreachable")

    def named_slot(self, name: str) -> LoginProfile:
        """The named slot, created under the pool lock when it does not exist yet."""
        with self._creating():
            return self.slot(name)

    def discard_unenrolled(self, profile: LoginProfile) -> None:
        """Remove a slot this enrollment created when no login was stored in it."""
        if not (profile.directory / "secret.json").exists():
            shutil.rmtree(profile.directory, ignore_errors=True)

    def acquire(
        self,
        hold: contextlib.ExitStack,
        *,
        settle_artifact: str | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        on_wait: Callable[[str], None] | None = None,
    ) -> LoginProfile:
        """Lock a free slot into ``hold``, waiting while every usable slot is busy.

        A settled slot is preferred. A slot with a pending journal belongs to an interrupted
        run: it is taken only when no settled slot is free and the journal names
        ``settle_artifact``, the plugin artifact this run brings, so the host can preserve
        that run's native state and settle it as a login's next run always has. Any other
        pending slot waits for ``recover``. With no slot enrolled, or none usable and none
        busy, waiting could never end, so those refuse instead.
        """
        announced = False
        while True:
            names = self.enrolled()
            if not names:
                raise KarnError("login_pool_empty:" + self.plugin_id)
            busy = 0
            settleable = None
            for name in names:
                profile = self.slot(name)
                attempt = contextlib.ExitStack()
                try:
                    attempt.enter_context(profile.exclusive())
                except LoginInUseError:
                    busy += 1
                    continue
                try:
                    enrolled = (profile.directory / "secret.json").is_file()
                    pending = profile.pending()
                except KarnError:
                    enrolled, pending = False, None
                if enrolled and pending is None:
                    if settleable is not None:
                        settleable[1].close()
                    hold.enter_context(attempt.pop_all())
                    return profile
                if (
                    enrolled
                    and settleable is None
                    and settle_artifact is not None
                    and pending.get("plugin_artifact") == settle_artifact
                ):
                    settleable = (profile, attempt)
                    continue
                attempt.close()
            if settleable is not None:
                hold.enter_context(settleable[1].pop_all())
                return settleable[0]
            if not busy:
                raise KarnError("login_pool_pending:" + self.plugin_id)
            if not announced:
                (on_wait or _announce)(
                    f"waiting for a login slot: all {busy} usable {self.plugin_id} slots are busy"
                )
                announced = True
            time.sleep(poll_seconds)


def adopt_legacy_login(state_root: Path, construct: str, plugin_id: str) -> bool:
    """Move a settled per-construct login into its plugin's pool, keeping the construct's name.

    Idempotent and safe against other hosts: the move happens under the legacy profile's own
    lock, as one rename, and never over an existing slot. A legacy login with a pending run
    stays where its run input names it, until recovering that run settles it.
    """
    if plugin_id not in LOGIN_PLUGINS or construct in LOGIN_PLUGINS:
        return False
    if not SLOT_NAME.fullmatch(construct):
        return False
    root = logins_root(state_root)
    legacy = root / construct
    if legacy.is_symlink() or not legacy.is_dir():
        return False
    try:
        # No O_CREAT: a directory that was never locked was never an enrolled profile.
        descriptor = os.open(legacy / "runner.lock", os.O_RDWR | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        try:
            # Another host may have moved the directory between the open and the lock.
            locked = os.path.samestat(
                os.fstat(descriptor), os.stat(legacy / "runner.lock", follow_symlinks=False)
            )
        except OSError:
            return False
        if (
            not locked
            or not (legacy / "secret.json").is_file()
            or (legacy / "active.json").exists()
            or (legacy / "plugin" / "mounted.json").exists()
        ):
            return False
        pool = LoginPool.of(state_root, plugin_id)
        target = pool.root / construct
        with pool._creating():
            # rename() would replace an empty directory, so the check and the move share a lock.
            if target.exists() or target.is_symlink():
                return False
            os.rename(legacy, target)
        _fsync_directory(root)
        _fsync_directory(pool.root)
        return True
    finally:
        os.close(descriptor)
