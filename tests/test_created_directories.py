"""Tests for :mod:`silverquillm.created_directories` — the directories one
invocation creates on the way to a path, removed again only on proof.

Both POSIX gaps are closed here and pinned here: a created directory's
identity comes from a descriptor opened on a private name, never from a
pathname, and the one deletion ever performed is of a private name, after
the identity proof, under the parent directory's lock.  Whatever cannot be
restored is reported, never hidden and never guessed at.
"""

from __future__ import annotations

import errno
import fcntl
import os
from pathlib import Path

import pytest

from silverquillm import created_directories as cd
from tests.fs_fixtures import names


def _entries(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir())


def _lock_is_held(directory: Path) -> bool:
    """Whether some other descriptor of *directory* holds its ``flock`` right
    now: a fresh descriptor cannot take it."""
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _identity(path: Path) -> tuple[int, int]:
    st = os.lstat(path)
    return (st.st_dev, st.st_ino)


def _hook_rename(monkeypatch: pytest.MonkeyPatch, *, before):
    """Run *before(src, dst, dir_fd)* ahead of every placement or move; it
    may raise to stand in for a failing rename."""
    real = cd.rename_noreplace

    def hooked(src, dst, *, dir_fd):
        before(src, dst, dir_fd)
        return real(src, dst, dir_fd=dir_fd)

    monkeypatch.setattr(cd, "rename_noreplace", hooked)


class TestEnsure:
    def test_creates_the_missing_chain_descriptor_first_under_the_locked_namespace(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c"
        made = cd.CreatedDirectories()
        with made.ensure(target) as entry:
            assert entry.created is not None and entry.created.path == target and entry.fd is not None
            assert _lock_is_held(target.parent), "the leaf's namespace stays locked for the block"
            assert not _lock_is_held(tmp_path), "an ancestor's lock is released once its component is settled"
            opened = os.fstat(entry.fd)
            assert entry.created.identity == (opened.st_dev, opened.st_ino) == _identity(target), (
                "the identity is the descriptor's, and the path names that very directory"
            )
        assert not _lock_is_held(target.parent)
        assert made.paths == (tmp_path / "a", tmp_path / "a" / "b", target)
        for directory in (tmp_path, tmp_path / "a", tmp_path / "a" / "b"):
            assert not [n for n in _entries(directory) if n.startswith(".")], "no private name is left behind"
        made.remove()
        assert not (tmp_path / "a").exists() and _entries(tmp_path) == []

    def test_an_existing_directory_is_opened_never_created_and_never_removed(self, tmp_path: Path) -> None:
        target = tmp_path / "x"
        target.mkdir()
        (target / "f").write_text("f", encoding="utf-8")
        made = cd.CreatedDirectories()
        with made.ensure(target) as entry:
            assert entry.created is None and not made and entry.fd is not None
            assert os.path.samestat(os.fstat(entry.fd), os.stat(target))
        made.remove()
        assert _entries(target) == ["f"]

    def test_a_directory_that_appears_before_placement_is_someone_elses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The private directory is made, opened and proven; then, in the
        instant before it is placed, someone puts a directory under the
        name.  The no-replace placement fails, theirs is used as found, and
        it is never this invocation's to remove."""
        target = tmp_path / "d"

        def intrude(src, dst, dir_fd) -> None:
            if names(dst, dir_fd, target):
                target.mkdir()
                (target / "theirs").write_text("not ours\n", encoding="utf-8")

        _hook_rename(monkeypatch, before=intrude)
        made = cd.CreatedDirectories()
        with made.ensure(target) as entry:
            assert entry.created is None and not made
            assert os.path.samestat(os.fstat(entry.fd), os.stat(target)), "what the path names now is what is handed over"
        made.remove()
        assert _entries(target) == ["theirs"] and _entries(tmp_path) == ["d"], "theirs is kept whole; the private directory is gone"

    def test_without_noreplace_the_fallback_still_places_and_removes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cd, "_renameat2", None)
        assert not cd.noreplace_available()
        target = tmp_path / "a" / "b"
        made = cd.CreatedDirectories()
        with made.ensure(target) as entry:
            assert entry.created is not None and _identity(target) == entry.created.identity
        made.remove()
        assert _entries(tmp_path) == []

    def test_an_absent_component_is_not_created_when_asked_not_to(self, tmp_path: Path) -> None:
        made = cd.CreatedDirectories()
        with made.ensure(tmp_path / "nope" / "deeper", create=False) as entry:
            assert entry.fd is None and entry.parent_fd is None and entry.created is None
        with made.ensure(tmp_path / "nope", create=False) as entry:
            assert entry.fd is None and entry.parent_fd is not None, "the parent exists and is locked; the leaf is absent"
            assert _lock_is_held(tmp_path)
        made.keep()
        assert not made and _entries(tmp_path) == []

    def test_a_component_that_is_a_file_refuses_with_nothing_created(self, tmp_path: Path) -> None:
        (tmp_path / "f").write_text("f", encoding="utf-8")
        made = cd.CreatedDirectories()
        with pytest.raises(cd.DirectoryCreationError, match="exists but is not a directory") as info, made.ensure(tmp_path / "f" / "x"):
            pass  # pragma: no cover - never entered
        assert info.value.path == tmp_path / "f" and not made and _entries(tmp_path) == ["f"]

    def test_a_creation_failure_leaves_nothing_of_the_failed_component(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "a" / "b" / "c"
        real = os.open

        def exhausted(path, flags, *a, **kw):
            if os.fsdecode(path).startswith(".c.creating-"):
                raise OSError(errno.EMFILE, "Too many open files")
            return real(path, flags, *a, **kw)

        monkeypatch.setattr(os, "open", exhausted)
        made = cd.CreatedDirectories()
        with pytest.raises(cd.DirectoryCreationError, match="cannot open it") as info, made.ensure(target):
            pass  # pragma: no cover - never entered
        failure = info.value
        assert failure.path == target and isinstance(failure.__cause__, OSError) and failure.__cause__.errno == errno.EMFILE
        assert _entries(tmp_path / "a" / "b") == [], "the private directory of the failed component is gone"
        assert made.paths == (tmp_path / "a", tmp_path / "a" / "b"), "the components created before it stay recorded"
        assert made.unwind(failure) is failure
        assert not (tmp_path / "a").exists(), "unwinding removes them"


class TestRemove:
    def _made(self, target: Path) -> cd.CreatedDirectories:
        made = cd.CreatedDirectories()
        made.make(target)
        assert made.paths[-1] == target
        return made

    def test_removal_holds_the_namespace_lock_and_deletes_only_a_private_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "r"
        made = self._made(target)
        seen: list[tuple[str, bool]] = []
        real = os.rmdir

        def observing(path, *a, dir_fd=None, **kw):
            seen.append((os.fsdecode(path), _lock_is_held(tmp_path)))
            return real(path, *a, dir_fd=dir_fd, **kw)

        monkeypatch.setattr(os, "rmdir", observing)
        made.remove()
        assert len(seen) == 1 and seen[0][0].startswith(".r.removing-") and seen[0][1], seen
        assert _entries(tmp_path) == []

    def test_a_replacement_in_the_instant_before_removal_is_moved_back_and_kept(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The identity check passes; then, as the entry is moved aside for
        removal, someone outside the protocol swaps it.  The swapped-in
        directory fails the proof under the private name, goes back where it
        was, and is reported — never deleted."""
        target, moved = tmp_path / "r", tmp_path / "moved-away"
        made = self._made(target)

        def swap(src, dst, dir_fd) -> None:
            if names(src, dir_fd, target):
                os.rename(target, moved)
                target.mkdir()
                (target / "theirs").write_text("not ours\n", encoding="utf-8")

        _hook_rename(monkeypatch, before=swap)
        with pytest.raises(cd.DirectoryCleanupError, match="no longer names") as info:
            made.remove()
        assert info.value.path == target
        assert _entries(target) == ["theirs"] and (target / "theirs").read_text(encoding="utf-8") == "not ours\n"
        assert _entries(moved) == [] and _entries(tmp_path) == ["moved-away", "r"], "ours stays where it went; nothing private is left"

    def test_a_replacement_before_the_identity_check_is_kept_and_never_moved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target, moved = tmp_path / "r", tmp_path / "moved-away"
        made = self._made(target)
        os.rename(target, moved)
        target.mkdir()
        moves: list[str] = []
        _hook_rename(monkeypatch, before=lambda src, dst, dir_fd: moves.append(src))
        with pytest.raises(cd.DirectoryCleanupError, match="no longer names"):
            made.remove()
        assert moves == [] and target.is_dir() and moved.is_dir()

    def test_a_directory_that_became_non_empty_is_kept_and_never_moved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "r"
        made = self._made(target)
        (target / "f").write_text("f", encoding="utf-8")
        moves: list[str] = []
        _hook_rename(monkeypatch, before=lambda src, dst, dir_fd: moves.append(src))
        with pytest.raises(cd.DirectoryCleanupError, match="not empty") as info:
            made.remove()
        assert info.value.path == target and moves == [] and _entries(target) == ["f"]

    def test_a_directory_moved_away_is_reported_not_forgotten(self, tmp_path: Path) -> None:
        target, moved = tmp_path / "r", tmp_path / "moved-away"
        made = self._made(target)
        os.rename(target, moved)
        with pytest.raises(cd.DirectoryCleanupError, match="moved away") as info:
            made.remove()
        assert info.value.path == target and moved.is_dir()

    def test_a_directory_removed_by_someone_else_leaves_nothing_to_report(self, tmp_path: Path) -> None:
        target = tmp_path / "r"
        made = self._made(target)
        os.rmdir(target)
        made.remove()
        assert _entries(tmp_path) == []

    def test_a_removal_that_fails_puts_the_very_directory_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "r"
        made = self._made(target)
        before = _identity(target)
        real = os.rmdir

        def denied(path, *a, dir_fd=None, **kw):
            if os.fsdecode(path).startswith(".r.removing-"):
                raise PermissionError(errno.EACCES, "Permission denied")
            return real(path, *a, dir_fd=dir_fd, **kw)

        monkeypatch.setattr(os, "rmdir", denied)
        with pytest.raises(cd.DirectoryCleanupError, match="could not be removed") as info:
            made.remove()
        assert info.value.path == target and f"rmdir {target}" in str(info.value) and isinstance(info.value.__cause__, PermissionError)
        assert _identity(target) == before and _entries(target) == [] and _entries(tmp_path) == ["r"]

    def test_a_move_aside_that_fails_keeps_the_directory_in_place(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "r"
        made = self._made(target)
        before = _identity(target)

        def denied(src, dst, dir_fd) -> None:
            if names(src, dir_fd, target):
                raise PermissionError(errno.EACCES, "Permission denied")

        _hook_rename(monkeypatch, before=denied)
        with pytest.raises(cd.DirectoryCleanupError, match="could not be removed") as info:
            made.remove()
        assert isinstance(info.value.__cause__, PermissionError) and _identity(target) == before and _entries(tmp_path) == ["r"]

    def test_a_move_back_that_fails_names_where_the_directory_is(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target, moved = tmp_path / "r", tmp_path / "moved-away"
        made = self._made(target)

        def swap_then_deny(src, dst, dir_fd) -> None:
            if names(src, dir_fd, target):
                os.rename(target, moved)
                target.mkdir()
                (target / "theirs").write_text("not ours\n", encoding="utf-8")
            elif os.fsdecode(src).startswith(".r.removing-"):
                raise PermissionError(errno.EACCES, "Permission denied")

        _hook_rename(monkeypatch, before=swap_then_deny)
        with pytest.raises(cd.DirectoryCleanupError, match="could not be moved back") as info:
            made.remove()
        aside = info.value.path
        assert aside.parent == tmp_path and aside.name.startswith(".r.removing-") and str(aside) in str(info.value)
        assert _entries(aside) == ["theirs"], "the swapped-in directory is kept where it is, whole"
        assert not target.exists() and _entries(moved) == []

    def test_an_inspection_failure_keeps_the_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "r"
        made = self._made(target)
        real = os.lstat

        def denied(path, *a, dir_fd=None, **kw):
            if dir_fd is not None and names(path, dir_fd, target):
                raise PermissionError(errno.EACCES, "Permission denied")
            return real(path, *a, dir_fd=dir_fd, **kw)

        monkeypatch.setattr(os, "lstat", denied)
        with pytest.raises(cd.DirectoryCleanupError, match="cannot be inspected") as info:
            made.remove()
        assert info.value.path == target and target.is_dir()

    def test_a_deletion_that_turns_out_not_to_be_the_created_directory_is_reported(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The backstop behind the private name: were the private entry
        swapped in the instant before ``rmdir``, the created directory's own
        descriptor still shows it linked, and that is said out loud."""
        target, moved = tmp_path / "r", tmp_path / "moved-away"
        made = self._made(target)
        real = os.rmdir

        def swapped(path, *a, dir_fd=None, **kw):
            if os.fsdecode(path).startswith(".r.removing-"):
                os.rename(path, "moved-away", src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
                os.mkdir(path, dir_fd=dir_fd)
            return real(path, *a, dir_fd=dir_fd, **kw)

        monkeypatch.setattr(os, "rmdir", swapped)
        with pytest.raises(cd.DirectoryCleanupError, match="was not the directory this invocation created"):
            made.remove()
        assert _entries(moved) == [] and not target.exists()


class TestUnwindAndKeep:
    def test_a_private_directory_that_cannot_be_discarded_is_reported_with_the_creation_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "a" / "c"
        real_open, real_rmdir = os.open, os.rmdir

        def exhausted(path, flags, *a, **kw):
            if os.fsdecode(path).startswith(".c.creating-"):
                raise OSError(errno.EMFILE, "Too many open files")
            return real_open(path, flags, *a, **kw)

        def denied(path, *a, dir_fd=None, **kw):
            if os.fsdecode(path).startswith(".c.creating-"):
                raise PermissionError(errno.EACCES, "Permission denied")
            return real_rmdir(path, *a, dir_fd=dir_fd, **kw)

        monkeypatch.setattr(os, "open", exhausted)
        monkeypatch.setattr(os, "rmdir", denied)
        made = cd.CreatedDirectories()
        with pytest.raises(cd.DirectoryCleanupError) as info, made.ensure(target):
            pass  # pragma: no cover - never entered
        kept = info.value
        assert kept.path.parent == tmp_path / "a" and kept.path.name.startswith(".c.creating-") and kept.path.is_dir()
        assert isinstance(kept.during, cd.DirectoryCreationError) and "cannot open it" in str(kept.during)
        assert isinstance(kept.__cause__, PermissionError) and f"rmdir {kept.path}" in str(kept)
        with pytest.raises(cd.DirectoryCleanupError, match="moreover") as more:
            made.unwind(kept)
        assert more.value.during is kept.during and (tmp_path / "a").is_dir(), "the ancestor holding the residue is kept with it"

    def test_keep_closes_every_descriptor_and_removes_nothing(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b"
        made = cd.CreatedDirectories()
        with made.ensure(target) as entry:
            fds = [entry.fd, entry.parent_fd, *(d.fd for d in made._created)]
        made.keep()
        assert not made and target.is_dir()
        for fd in fds:
            with pytest.raises(OSError):
                os.fstat(fd)
        made.remove()
        assert target.is_dir(), "nothing is recorded any more, so nothing is removed"
