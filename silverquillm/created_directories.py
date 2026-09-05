"""Directories one invocation creates on the way to a path, removed again only
on proof.

The promote and publish gates create a directory when the path they are given
is absent — ``candidates/``, the publication destination, any missing
ancestor — and must remove exactly those again when the invocation ends with
nothing in them.  POSIX makes both halves treacherous: ``mkdir`` returns no
descriptor, so the inode found under the name afterwards need not be the one
created, and ``rmdir`` works by name, so the entry removed need not be the one
inspected.  This module closes both gaps and reports, rather than hides,
whatever it cannot restore.

**Creation is descriptor-first.**  A component is created under a private
random name beside its final one (``.<name>.creating-<nonce>``), opened
without following a link, and its identity (device and inode) taken from that
descriptor; only then is it moved into place with
``renameat2(RENAME_NOREPLACE)``, which fails rather than replace anything that
appeared under the name meanwhile — then the directory there is not this
invocation's, and the private one is removed again.  The identity of a created
directory therefore never comes from a pathname.  Where the platform offers no
``RENAME_NOREPLACE`` (Linux before 3.15, a C library without ``renameat2``,
other systems) a plain rename places it, and the namespace lock below is what
keeps that instant safe against every cooperating invocation.

**Removal is by private name too.**  A created directory is removed only
after it is proven, under the namespace lock, still to be the very directory
created — the path names its device and inode, and the held descriptor pins
that inode, so it cannot have been freed and reused — and empty.  It is then
moved back to a private name (``.<name>.removing-<nonce>``) and ``rmdir``'d
there, so the one deletion this module ever performs is of a name nobody else
knows, proven once more after the move; a directory that turns out, after the
move, not to be the created one or not to be empty is moved back into place
(``RENAME_NOREPLACE`` again) and reported, never deleted.

**The namespace is serialized.**  Every creation, inspection, placement and
removal of a component runs under an exclusive advisory ``flock`` on its
parent directory's own descriptor, held across those few system calls, and
every operation is relative to that descriptor (``dir_fd``), so a renamed or
replaced ancestor cannot redirect them.  Cooperating invocations — every
promote and publish invocation — therefore never interleave inside a creation
or a removal, and one that finds the directory present treats it as someone
else's.  The lock leaves no artifact.

**What is not restored is reported.**  Anything short of a proven removal — a
directory that cannot be inspected or removed, one no longer the directory
created, one no longer empty, a moved-aside directory that cannot be moved
back — raises :class:`DirectoryCleanupError` naming the path concerned and
what to do, and the owner surfaces it instead of reporting a clean refusal.  A
crash between creating a private-name directory and placing it leaves an
empty dot-prefixed directory beside the destination, which git does not see
and any operator may remove.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import fcntl
import os
import secrets
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
#: A directory this invocation just made under a private name: never reached
#: through a link.
_CREATED = _DIRECTORY | os.O_NOFOLLOW
_RENAME_NOREPLACE = 1
#: ``renameat2`` reporting that the kernel or filesystem cannot honour the flag.
_NOREPLACE_UNSUPPORTED = frozenset({errno.EINVAL, errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP})
_PRIVATE_NAME_ATTEMPTS = 8


class CreatedDirectoryError(Exception):
    """Something about a directory this invocation creates is not as it
    should be; ``path`` names the directory concerned."""

    def __init__(self, message: str, *, path: Path) -> None:
        super().__init__(message)
        self.path = Path(path)


class DirectoryCreationError(CreatedDirectoryError):
    """A component on the way to the path could not be created, or, once
    created under its private name, could not be opened, proven or placed —
    and nothing of that component is left.  Components created before it
    stay recorded on their :class:`CreatedDirectories` for the owner to
    remove."""


class DirectoryCleanupError(CreatedDirectoryError):
    """A directory this invocation created is not restored: it is kept where
    the message says (at its path, or moved aside under a private name it
    could not be moved back from), or what the path names is someone else's
    and is kept.  The message says what to do.  *during* is the creation
    failure that was being unwound when cleanup failed, if any."""

    def __init__(self, message: str, *, path: Path, during: DirectoryCreationError | None = None) -> None:
        super().__init__(message, path=path)
        self.during = during


@dataclass(frozen=True)
class CreatedDirectory:
    """One directory this invocation created: where it was placed (*path*, for
    messages; *name* relative to *parent_fd*, the namespace it lives in), the
    open descriptor of the directory itself and its identity."""

    path: Path
    name: str
    parent_fd: int
    fd: int
    identity: tuple[int, int]


@dataclass(frozen=True)
class Entry:
    """The directory at the path :meth:`CreatedDirectories.ensure` was given,
    handed over while its namespace — *parent_fd*, the parent directory — is
    locked.  *fd* is a borrowed descriptor of it, valid for the block (``None``
    when nothing is there and nothing was to be created); *created* is its
    record when this invocation made it."""

    fd: int | None
    parent_fd: int | None
    name: str
    created: CreatedDirectory | None


def _load_renameat2():
    try:
        fn = ctypes.CDLL(None, use_errno=True).renameat2
    except (OSError, AttributeError):
        return None
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    return fn


_renameat2 = _load_renameat2()


def rename_noreplace(src: str, dst: str, *, dir_fd: int) -> None:
    """Rename *src* to *dst*, both relative to *dir_fd*.  Where the platform
    can promise it (``renameat2`` with ``RENAME_NOREPLACE``) the rename fails
    with :class:`FileExistsError` rather than replace anything at *dst*;
    elsewhere it is a plain rename, which replaces an empty directory at
    *dst*, and callers rely on the namespace lock for that instant."""
    if _renameat2 is not None:
        if _renameat2(dir_fd, os.fsencode(src), dir_fd, os.fsencode(dst), _RENAME_NOREPLACE) == 0:
            return
        code = ctypes.get_errno()
        if code not in _NOREPLACE_UNSUPPORTED:
            raise OSError(code, os.strerror(code), src, None, dst)
    os.rename(src, dst, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)


def noreplace_available() -> bool:
    """Whether placements and move-backs refuse to replace (``renameat2`` is
    present) — reported by callers' documentation, never decided on."""
    return _renameat2 is not None


@contextlib.contextmanager
def _locked(dir_fd: int) -> Iterator[None]:
    """The namespace lock: an exclusive advisory ``flock`` on a directory's
    own descriptor, held across a few system calls on its entries."""
    fcntl.flock(dir_fd, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(dir_fd, fcntl.LOCK_UN)


def _components(path: Path) -> tuple[str, list[tuple[str, Path]]]:
    """The anchor to open first (``/`` or the working directory) and *path*'s
    components under it, outermost first, each with the path it names."""
    chain = [*reversed(path.parents), path]
    components = [(p.name, p) for p in chain if p.name]
    if not components:
        components = [(".", path)]
    return ("/" if path.is_absolute() else "."), components


class CreatedDirectories:
    """The directories one invocation created on the way to a path — none
    when the path already existed — with the proof it needs to remove exactly
    those again, and nothing else.

    :meth:`ensure` creates what is missing and yields the directory at the
    path under its namespace lock; :meth:`remove` removes every directory
    created, innermost first, each only on proof, and raises
    :class:`DirectoryCleanupError` for the first it cannot restore;
    :meth:`keep` releases everything and removes nothing.  One of the two
    ends every use."""

    def __init__(self) -> None:
        self._created: list[CreatedDirectory] = []
        self._opened: list[int] = []

    def __bool__(self) -> bool:
        return bool(self._created)

    @property
    def paths(self) -> tuple[Path, ...]:
        """The directories this invocation created, outermost first."""
        return tuple(d.path for d in self._created)

    @property
    def innermost(self) -> CreatedDirectory | None:
        return self._created[-1] if self._created else None

    @contextlib.contextmanager
    def ensure(self, path: Path, *, create: bool = True) -> Iterator[Entry]:
        """Open *path* component by component from its anchor, creating each
        missing one (unless *create* is false) under its parent's namespace
        lock, and yield the directory at *path* while its own namespace stays
        locked — the caller does there what must be atomic with the creation.
        A component that exists is opened as the caller's own path resolution
        would (a link followed), never created, never later removed.  Fails
        with :class:`DirectoryCreationError` (nothing left of the failed
        component; earlier ones stay recorded here) or, when even the private
        directory of a failed creation cannot be removed, with
        :class:`DirectoryCleanupError`."""
        path = Path(path)
        anchor, components = _components(path)
        try:
            cur = os.open(anchor, _DIRECTORY)
        except OSError as exc:
            raise DirectoryCreationError(f"cannot open {anchor!r} to reach {path}: {exc.strerror or exc}", path=path) from exc
        self._opened.append(cur)
        for name, display in components[:-1]:
            with _locked(cur):
                opened = self._enter(cur, name, display, create=create)
            if opened is None:
                yield Entry(fd=None, parent_fd=None, name=components[-1][0], created=None)
                return
            cur = opened
        name, display = components[-1]
        with _locked(cur):
            fd = self._enter(cur, name, display, create=create)
            made = self.innermost
            if made is not None and (fd is None or made.fd != fd):
                made = None
            yield Entry(fd=fd, parent_fd=cur, name=name, created=made)

    def make(self, path: Path) -> None:
        """:meth:`ensure` with nothing to do under the lock: create what is
        missing of *path* and release its namespace."""
        with self.ensure(path):
            pass

    def unwind(self, failure: CreatedDirectoryError) -> DirectoryCreationError:
        """*failure* ended a creation under way: remove what had been created
        before it and return the creation failure for the owner to report.
        Raises :class:`DirectoryCleanupError` (``during`` naming that creation
        failure) when the tree is not restored — by *failure* itself, or by
        this removal."""
        during = failure.during if isinstance(failure, DirectoryCleanupError) else failure
        try:
            self.remove()
        except DirectoryCleanupError as kept:
            if isinstance(failure, DirectoryCleanupError):
                raise DirectoryCleanupError(f"{failure}; moreover, {kept}", path=failure.path, during=during) from kept
            raise DirectoryCleanupError(str(kept), path=kept.path, during=during) from kept
        if isinstance(failure, DirectoryCleanupError):
            raise failure
        return failure

    def remove(self) -> None:
        """Remove every directory this invocation created, innermost first,
        each only while proven still the one created and empty, then release
        every descriptor.  The first directory that cannot be restored stops
        the removal and is reported as :class:`DirectoryCleanupError`; the
        ones outside it are its ancestors and are kept with it."""
        try:
            while self._created:
                token = self._created[-1]
                self._remove_one(token)
                self._created.pop()
                os.close(token.fd)
        finally:
            self.keep()

    def keep(self) -> None:
        """Release every descriptor and remove nothing: the directories are
        in use, or they are evidence."""
        fds = [d.fd for d in self._created] + self._opened
        self._created.clear()
        self._opened.clear()
        for fd in fds:
            with contextlib.suppress(OSError):
                os.close(fd)

    # -- creation, under the parent's namespace lock ------------------------

    def _enter(self, parent_fd: int, name: str, display: Path, *, create: bool) -> int | None:
        try:
            fd = os.open(name, _DIRECTORY, dir_fd=parent_fd)
        except FileNotFoundError:
            if not create:
                return None
        except NotADirectoryError as exc:
            raise DirectoryCreationError(f"{display} exists but is not a directory", path=display) from exc
        except OSError as exc:
            raise DirectoryCreationError(f"cannot open {display}: {exc.strerror or exc}", path=display) from exc
        else:
            self._opened.append(fd)
            return fd
        return self._create(parent_fd, name, display)

    def _create(self, parent_fd: int, name: str, display: Path) -> int:
        private = self._make_private_directory(parent_fd, name, display)
        try:
            fd = os.open(private, _CREATED, dir_fd=parent_fd)
        except OSError as exc:
            failure = DirectoryCreationError(f"created {display} but cannot open it: {exc.strerror or exc}", path=display)
            self._discard_private(parent_fd, private, display, failure)
            raise failure from exc
        try:
            made = os.fstat(fd)
            rename_noreplace(private, name, dir_fd=parent_fd)
        except FileExistsError as exc:
            # Something appeared under the name in the instant — not this
            # invocation's.  Use it as found, or refuse if it cannot be used.
            os.close(fd)
            failure = DirectoryCreationError(f"{display} appeared while this invocation was creating it and cannot be opened as a directory", path=display)
            self._discard_private(parent_fd, private, display, failure)
            found = self._enter(parent_fd, name, display, create=False)
            if found is None:
                raise failure from exc
            return found
        except OSError as exc:
            os.close(fd)
            failure = DirectoryCreationError(f"cannot create {display}: {exc.strerror or exc}", path=display)
            self._discard_private(parent_fd, private, display, failure)
            raise failure from exc
        self._created.append(CreatedDirectory(path=display, name=name, parent_fd=parent_fd, fd=fd, identity=(made.st_dev, made.st_ino)))
        return fd

    def _make_private_directory(self, parent_fd: int, name: str, display: Path) -> str:
        """An empty directory under a fresh private name beside *name*."""
        for _ in range(_PRIVATE_NAME_ATTEMPTS):
            private = f".{name}.creating-{secrets.token_hex(4)}"
            try:
                os.mkdir(private, 0o777, dir_fd=parent_fd)
            except FileExistsError:
                continue
            except OSError as exc:
                raise DirectoryCreationError(f"cannot create {display}: {exc.strerror or exc}", path=display) from exc
            return private
        raise DirectoryCreationError(f"cannot create {display}: no free private name beside it", path=display)

    def _discard_private(self, parent_fd: int, private: str, display: Path, failure: DirectoryCreationError) -> None:
        """Remove the private-name directory of a creation that did not
        complete — a name nobody else knows, so by name is safe — or report
        it as residue."""
        try:
            os.rmdir(private, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        except OSError as exc:
            left = display.parent / private
            raise DirectoryCleanupError(
                f"{failure}; the private directory {left} it had made could not be removed ({exc.strerror or exc}) and is"
                f" kept — remove it by hand (rmdir {left})",
                path=left,
                during=failure,
            ) from exc

    # -- removal, under the parent's namespace lock -------------------------

    def _remove_one(self, token: CreatedDirectory) -> None:
        path, name, parent_fd = token.path, token.name, token.parent_fd
        with _locked(parent_fd):
            if not self._still_in_place(token):
                return
            try:
                entries = os.listdir(token.fd)
            except OSError as exc:
                raise DirectoryCleanupError(
                    f"the directory {path} this invocation created cannot be inspected ({exc.strerror or exc}) and may be"
                    f" left behind — check it and remove it by hand if it is empty (rmdir {path})",
                    path=path,
                ) from exc
            if entries:
                raise DirectoryCleanupError(
                    f"the directory {path} this invocation created is not empty — something else wrote into it meanwhile;"
                    " it is kept with its contents, which are not this invocation's to remove — inspect it by hand",
                    path=path,
                )
            private = self._reserve_private_name(parent_fd, name, path)
            try:
                rename_noreplace(name, private, dir_fd=parent_fd)
            except OSError as exc:
                raise DirectoryCleanupError(
                    f"the empty directory {path} this invocation created could not be removed ({exc.strerror or exc});"
                    f" remove it by hand (rmdir {path})",
                    path=path,
                ) from exc
            self._remove_moved(token, private)

    def _still_in_place(self, token: CreatedDirectory) -> bool:
        """Whether *token*'s path still names the very directory created.
        ``False`` when it is gone and nothing of it remains anywhere; anything
        else that is not the created directory in place is reported."""
        path = token.path
        try:
            now = os.lstat(token.name, dir_fd=token.parent_fd)
        except FileNotFoundError:
            if os.fstat(token.fd).st_nlink:
                raise DirectoryCleanupError(
                    f"the directory {path} this invocation created was moved away from that path meanwhile and remains"
                    " wherever it went — find and inspect it by hand",
                    path=path,
                ) from None
            return False
        except OSError as exc:
            raise DirectoryCleanupError(
                f"the directory {path} this invocation created cannot be inspected ({exc.strerror or exc}) and may be"
                f" left behind — check it and remove it by hand if it is empty (rmdir {path})",
                path=path,
            ) from exc
        if not stat.S_ISDIR(now.st_mode) or (now.st_dev, now.st_ino) != token.identity:
            raise DirectoryCleanupError(
                f"{path} no longer names the empty directory this invocation created; what is there now is someone"
                " else's and is kept — inspect it by hand",
                path=path,
            )
        return True

    def _reserve_private_name(self, parent_fd: int, name: str, display: Path) -> str:
        """A fresh private name beside *name* with nothing under it, for the
        entry at *name* to be moved to."""
        for _ in range(_PRIVATE_NAME_ATTEMPTS):
            private = f".{name}.removing-{secrets.token_hex(4)}"
            try:
                os.lstat(private, dir_fd=parent_fd)
            except FileNotFoundError:
                return private
            except OSError as exc:
                raise DirectoryCleanupError(
                    f"the empty directory {display} this invocation created could not be removed (cannot reserve a"
                    f" private name beside it: {exc.strerror or exc}); remove it by hand (rmdir {display})",
                    path=display,
                ) from exc
        raise DirectoryCleanupError(
            f"the empty directory {display} this invocation created could not be removed (no free private name beside"
            f" it); remove it by hand (rmdir {display})",
            path=display,
        )

    def _remove_moved(self, token: CreatedDirectory, private: str) -> None:
        """The entry that was at the path now sits under *private*: prove it
        the created directory once more and remove it there; anything else is
        moved back and reported."""
        path, parent_fd = token.path, token.parent_fd
        try:
            moved = os.lstat(private, dir_fd=parent_fd)
        except OSError as exc:
            self._move_back(token, private)
            raise DirectoryCleanupError(
                f"the directory {path} this invocation created cannot be inspected ({exc.strerror or exc}) and is kept —"
                f" check it and remove it by hand if it is empty (rmdir {path})",
                path=path,
            ) from exc
        if not stat.S_ISDIR(moved.st_mode) or (moved.st_dev, moved.st_ino) != token.identity:
            self._move_back(token, private)
            raise DirectoryCleanupError(
                f"{path} no longer names the empty directory this invocation created; what is there now is someone"
                " else's and is kept — inspect it by hand",
                path=path,
            )
        try:
            os.rmdir(private, dir_fd=parent_fd)
        except OSError as exc:
            self._move_back(token, private)
            if exc.errno in (errno.ENOTEMPTY, errno.EEXIST):
                message = (
                    f"the directory {path} this invocation created is not empty — something else wrote into it meanwhile;"
                    " it is kept with its contents, which are not this invocation's to remove — inspect it by hand"
                )
            else:
                message = (
                    f"the empty directory {path} this invocation created could not be removed ({exc.strerror or exc});"
                    f" remove it by hand (rmdir {path})"
                )
            raise DirectoryCleanupError(message, path=path) from exc
        if os.fstat(token.fd).st_nlink:
            raise DirectoryCleanupError(
                f"what was removed for {path} was not the directory this invocation created, which is still linked"
                " somewhere — a directory that was not this invocation's is gone; find where its own went and inspect by hand",
                path=path,
            )

    def _move_back(self, token: CreatedDirectory, private: str) -> None:
        """Return the moved-aside entry to the path it came from; failing
        that, report where it is."""
        path = token.path
        try:
            rename_noreplace(private, token.name, dir_fd=token.parent_fd)
        except OSError as exc:
            aside = path.parent / private
            raise DirectoryCleanupError(
                f"what was at {path} was moved to {aside} for removal and could not be moved back"
                f" ({exc.strerror or exc}); it is kept there, untouched — inspect it and move it back by hand"
                f" (mv {aside} {path})",
                path=aside,
            ) from exc
