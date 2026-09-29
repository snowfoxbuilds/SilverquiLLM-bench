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

from .definition import KarnError, canonical, read_regular, strict_json
from .login import LOGIN_PLUGINS, LoginInUseError, LoginProfile, private_directory, write_private

SLOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
DEFAULT_POLL_SECONDS = 5.0
SLOT_RECORD = "pool.json"
# A secret file holds one JSON string of at most 64 KiB, escaped: the bound its store keeps.
SECRET_FILE_LIMIT = 2 * 65536 + 2
# What each plugin's store keeps in its secret document: the login file it requires, and
# every file it may hold. The two sets are disjoint, so a document names its plugin.
STORED_LOGIN_FILES = {
    "karn-codex-login": ("auth.json", frozenset({"auth.json"})),
    "karn-claude-login": (".credentials.json", frozenset({".credentials.json", ".claude.json"})),
}


class LoginPoolUnavailableError(KarnError):
    """No slot can ever serve this run until the operator enrolls or recovers one."""


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


def recorded_plugin(directory: Path) -> str | None:
    """The plugin a slot was created for, or None when its record is missing or malformed."""
    try:
        value = strict_json(read_regular(directory / SLOT_RECORD, limit=4096))
    except KarnError:
        return None
    return value.get("plugin_id") if isinstance(value, dict) else None


def stored_login_plugin(document: object) -> str | None:
    """The plugin whose store wrote this secret document, judged by its exact shape."""
    try:
        value = strict_json(document.encode()) if isinstance(document, str) else None
    except (KarnError, UnicodeError):
        # A tampered secret can carry a lone surrogate, which no store ever writes.
        return None
    if not isinstance(value, dict) or set(value) != {"format", "revision", "files"}:
        return None
    revision, files = value["revision"], value["files"]
    if (
        value["format"] != 1
        or not isinstance(revision, str)
        or not re.fullmatch(r"[0-9a-f]{32}", revision)
        or not isinstance(files, dict)
        or not all(isinstance(content, str) for content in files.values())
    ):
        return None
    for plugin_id, (required, allowed) in STORED_LOGIN_FILES.items():
        if required in files and set(files) <= allowed:
            return plugin_id
    return None


def stored_secret_plugin(directory: Path) -> str:
    """The plugin whose store wrote the secret document in ``directory``.

    The file is read with its store's bound and never followed through a link. A failure
    names only what is wrong with the file, never its content.
    """
    try:
        raw = read_regular(directory / "secret.json", limit=SECRET_FILE_LIMIT)
    except KarnError:
        raise KarnError("login_secret_unreadable") from None
    try:
        document = strict_json(raw)
    except KarnError:
        raise KarnError("login_secret_malformed") from None
    owner = stored_login_plugin(document)
    if owner is None:
        raise KarnError("login_secret_unrecognized")
    return owner


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
        """The slot a run names.

        A removed slot's directory may be recreated here, harmlessly: without its pool
        record and secret it is never allocated, and its lock file is a new one.
        """
        if not SLOT_NAME.fullmatch(name):
            raise KarnError("invalid_login_slot")
        return LoginProfile(self.root / name, name)

    @contextlib.contextmanager
    def _creating(self):
        """Serialize creating, adopting and discarding slots, which all change the pool root."""
        descriptor = os.open(
            self.root / ".pool.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)

    def _claim(self, name: str) -> LoginProfile:
        profile = self.slot(name)
        recorded = recorded_plugin(profile.directory)
        if recorded is None and (profile.directory / "secret.json").exists():
            raise KarnError("login_slot_unrecorded")
        if recorded not in (None, self.plugin_id):
            raise KarnError("login_slot_belongs_to_other_plugin")
        if recorded is None:
            write_private(profile.directory / SLOT_RECORD, canonical({"plugin_id": self.plugin_id}))
        return profile

    def enrolled(self) -> list[str]:
        """Slots of this plugin holding a stored login; an unfinished enrollment is not one."""
        names = []
        for entry in sorted(self.root.iterdir()):
            if (
                SLOT_NAME.fullmatch(entry.name)
                and entry.is_dir()
                and not entry.is_symlink()
                and (entry / "secret.json").is_file()
                and recorded_plugin(entry) == self.plugin_id
            ):
                names.append(entry.name)
        return names

    def new_slot(self) -> LoginProfile:
        """Claim the lowest unused ``slot-N``; mkdir is the claim, so two enrollments never share."""
        with self._creating():
            for number in itertools.count(1):
                name = f"slot-{number}"
                try:
                    os.mkdir(self.root / name, 0o700)
                except FileExistsError:
                    continue
                return self._claim(name)
        raise AssertionError("unreachable")

    def named_slot(self, name: str) -> LoginProfile:
        """The named slot of this pool, created when it does not exist yet."""
        with self._creating():
            return self._claim(name)

    def discard_unenrolled(self, profile: LoginProfile) -> None:
        """Remove a slot this enrollment created, only if no login was stored in it.

        The check and the removal happen under the slot's own lock, so a concurrent
        enrollment of the same name either holds the slot (and it is kept) or finds it gone.
        """
        with self._creating(), contextlib.suppress(LoginInUseError), profile.exclusive():
            if not (profile.directory / "secret.json").exists():
                shutil.rmtree(profile.directory)

    def acquire(
        self,
        hold: contextlib.ExitStack,
        *,
        settle_artifact: str | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        on_wait: Callable[[str], None] | None = None,
    ) -> LoginProfile:
        """Lock a free slot into ``hold``, waiting while every usable slot is busy.

        A settled slot is preferred once its stored login is read, unchanged, and found to
        have this pool's plugin's shape; a damaged one is skipped instead of failing the run
        it would serve. A slot with a pending journal belongs to an interrupted run: it is
        taken only when no settled slot is free and the journal names ``settle_artifact``,
        the plugin artifact this run brings, so the host can preserve that run's native state
        and settle it as a login's next run always has. Its stored login is left for that
        plugin to judge. Any other pending slot waits for ``recover``. With no slot enrolled,
        or none usable and none busy, waiting could never end, so those refuse instead.
        """
        report = on_wait or _announce
        announced, skipped = False, set()

        def skip(name: str, error: Exception) -> None:
            # One damaged slot must not stop the pool; the operator is told once.
            if name not in skipped:
                skipped.add(name)
                report(f"skipping login slot {self.plugin_id}/{name}: {error}")

        while True:
            names = self.enrolled()
            if not names:
                raise LoginPoolUnavailableError("login_pool_empty:" + self.plugin_id)
            busy = damaged_logins = 0
            # Every lock taken while choosing is released here unless handed to ``hold``.
            with contextlib.ExitStack() as candidates:
                settleable = None
                for name in names:
                    lock = contextlib.ExitStack()
                    try:
                        profile = self.slot(name)
                        lock.enter_context(profile.exclusive())
                    except LoginInUseError:
                        busy += 1
                        continue
                    except (KarnError, OSError) as error:
                        skip(name, error)
                        continue
                    candidates.enter_context(lock)
                    try:
                        pending = profile.pending()
                    except KarnError as error:
                        skip(name, error)
                        continue
                    if pending is None:
                        try:
                            if stored_secret_plugin(profile.directory) != self.plugin_id:
                                raise KarnError("login_secret_belongs_to_other_plugin")
                        except KarnError as error:
                            damaged_logins += 1
                            skip(name, error)
                            continue
                        hold.enter_context(lock.pop_all())
                        return profile
                    if (
                        settleable is None
                        and settle_artifact is not None
                        and pending.get("plugin_artifact") == settle_artifact
                    ):
                        settleable = (profile, lock)
                if settleable is not None:
                    hold.enter_context(settleable[1].pop_all())
                    return settleable[0]
            if not busy:
                # Only a damaged login needs re-enrolling; anything else waits for recovery.
                reason = "unusable" if damaged_logins == len(names) else "pending"
                raise LoginPoolUnavailableError(f"login_pool_{reason}:{self.plugin_id}")
            if not announced:
                report(
                    f"waiting for a login slot: all {busy} usable {self.plugin_id} slots are busy"
                )
                announced = True
            time.sleep(poll_seconds)


def adopt_legacy_login(state_root: Path, construct: str, plugin_id: str) -> str:
    """Move one per-construct login from before pools into its plugin's pool, by the operator.

    The login must be settled and its stored document must be the one ``plugin_id``'s store
    writes, so a login enrolled through another plugin can never join this pool. The move
    happens under the legacy profile's own lock, as one rename that never replaces a slot.
    Returns the slot's name as runs record it.
    """
    if plugin_id not in LOGIN_PLUGINS:
        raise KarnError("invalid_login_pool")
    if construct in LOGIN_PLUGINS or not SLOT_NAME.fullmatch(construct):
        raise KarnError("invalid_legacy_login")
    root = logins_root(state_root)
    legacy = root / construct
    if legacy.is_symlink() or not legacy.is_dir():
        raise KarnError("legacy_login_not_found")
    try:
        # No O_CREAT: a directory that was never locked was never an enrolled profile.
        descriptor = os.open(legacy / "runner.lock", os.O_RDWR | os.O_NOFOLLOW)
    except OSError:
        raise KarnError("legacy_login_not_found") from None
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LoginInUseError("login_in_use") from None
        try:
            # Another adoption may have moved the directory between the open and the lock.
            locked = os.path.samestat(
                os.fstat(descriptor), os.stat(legacy / "runner.lock", follow_symlinks=False)
            )
        except OSError:
            locked = False
        if not locked:
            raise KarnError("legacy_login_not_found")
        if (legacy / "active.json").exists() or (legacy / "plugin" / "mounted.json").exists():
            raise KarnError("legacy_login_pending")
        try:
            owner = stored_secret_plugin(legacy)
        except KarnError as error:
            if str(error) == "login_secret_unrecognized":
                raise KarnError("legacy_login_unrecognized") from None
            raise KarnError("legacy_login_not_enrolled") from None
        if owner != plugin_id:
            raise KarnError("legacy_login_belongs_to_other_plugin")
        pool = LoginPool.of(state_root, plugin_id)
        target = pool.root / construct
        # The record goes in first, so a crash leaves a legacy login, never an unrecorded slot.
        write_private(legacy / SLOT_RECORD, canonical({"plugin_id": plugin_id}))
        with pool._creating():
            # rename() would replace an empty directory, so the check and the move share a lock.
            if target.exists() or target.is_symlink():
                raise KarnError("login_slot_exists")
            os.rename(legacy, target)
        _fsync_directory(root)
        _fsync_directory(pool.root)
        return f"{plugin_id}/{construct}"
    finally:
        os.close(descriptor)
