"""Port a benchmark from the Known-Best Workspace (KNOWN-BEST-ENGINE.md › Building a benchmark from it).

Usage::

    python3 scripts/port_from_known_best.py BENCHMARK            # rewrite the ported paths
    python3 scripts/port_from_known_best.py --check BENCHMARK    # exit 1 if porting would change anything

Porting hard-copies ``known_best/`` into ``benchmarks/<BENCHMARK>/`` and owns
exactly these paths, which it replaces wholesale:

- ``workspace/`` and ``data/test_oracle_workspace/``: ``engine/``, ``cards/fdn/``,
  the ``cards/`` package files, ``conftest.py``, ``pytest.ini``, ``test_utils.py``
  and the Test Interface (``test_interface.py``, its ``.md`` and its demonstration tests);
- ``workspace/engine_tests/``: the Audited Engine Tests, seeding the Engine Reference Tests;
- ``data/tests/audited/fdn/`` and ``data/tests/audited/engine/``;
- the Test Oracle Workspace's mirrors of the Workspace's ``AGENTS.md`` and ``skills/``
  and of every ``data/tests/audited/**/tests.py``.

Owned paths are synchronized, not merged: a ``cards/`` package file removed from
the Known-Best Workspace, or an ``AGENTS.md`` / ``skills/`` removed from the
Workspace, disappears from the ported trees too.

Every other path is the benchmark's own and is left alone: its agent documents,
its target cards outside ``cards/fdn/`` and their Audited Tests.

Each target card (``config.json``) becomes a behavior-free stub in the Workspace,
generated from its Card Spec by ``scripts/generate_printed_classes.py``; an FDN
target also loses its FDN Reference Test there and keeps its Known-Best
implementation in the Test Oracle Workspace.

Patches are unified diffs with paths relative to the tree they patch, applied in
order with exact context; a patch that no longer applies fails the port, and so
does a malformed one (a header without hunks, a hunk whose lines do not add up
to its declared counts), a deletion that would leave content behind, or a path
that is absolute or leads out of the tree. The whole port is built in a staging
copy and published only once every step has succeeded, so any failure — a
failing patch, a missing Card Spec, a stale manifest — changes nothing:

- ``data/known_defects/<id>.patch``: one per Known Defect, in manifest order,
  applied to the Workspace — the baseline is the Known-Best Workspace plus its
  Known Defects;
- ``data/oracle_patches/*.patch``: the oracle's engine extensions, in file-name
  order, applied to the Test Oracle Workspace.

To record or refresh a patch, port, edit the ported tree, and diff it against
the tree before the edit (``git diff --no-index --relative``), keeping each
Known Defect to its own patch.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_printed_classes import render  # noqa: E402
from scripts.oracle_support import load_layout  # noqa: E402

KNOWN_BEST = ROOT / "known_best"
ORACLE = Path("data/test_oracle_workspace")
DEFECT_PATCHES = Path("data/known_defects")
ORACLE_PATCHES = Path("data/oracle_patches")
WORKSPACE_ITEMS = (
    "engine", "cards/fdn", "conftest.py", "pytest.ini", "test_utils.py",
    "test_interface.py", "test_interface.md", "test_test_interface.py",
)
AUDITED_ITEMS = ("fdn", "engine")
_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
_CACHES = ("__pycache__", ".pytest_cache")


class PortError(Exception):
    """The benchmark cannot be ported as configured."""


# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# Git's per-file metadata lines, allowed between file sections.
_METADATA = ("diff ", "index ", "new file mode", "deleted file mode", "old mode", "new mode",
             "similarity index", "rename from", "rename to", "Binary files")


@dataclass
class _Hunk:
    old_start: int
    old_count: int
    old: list[str]
    new: list[str]


def _patch_path(header: str) -> str | None:
    path = header.split("\t", 1)[0].strip()
    if path == "/dev/null":
        return None
    return path.split("/", 1)[1] if path.startswith(("a/", "b/")) else path


def _parse_patch(text: str) -> list[tuple[str | None, str | None, list[_Hunk]]]:
    """``[(old path, new path, hunks)]``, refusing anything that is not a
    well-formed unified diff: unpaired headers, files without hunks, hunks
    whose lines do not add up to their declared counts, and stray text."""
    files: list[tuple[str | None, str | None, list[_Hunk]]] = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(_METADATA) or not line.strip():
            i += 1
            continue
        if not line.startswith("--- "):
            raise PortError(f"line {i + 1}: expected a file header, found {line.rstrip()!r}")
        if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
            raise PortError(f"line {i + 1}: '---' header without its '+++' header")
        old, new = _patch_path(line[4:]), _patch_path(lines[i + 1][4:])
        if old is None and new is None:
            raise PortError(f"line {i + 1}: both paths are /dev/null")
        i += 2
        hunks: list[_Hunk] = []
        while i < len(lines) and lines[i].startswith("@@"):
            hunk, i = _parse_hunk(lines, i)
            hunks.append(hunk)
        if not hunks:
            raise PortError(f"{new or old}: file header without hunks")
        files.append((old, new, hunks))
    if not files:
        raise PortError("patch holds no file changes")
    return files


def _parse_hunk(lines: list[str], i: int) -> tuple[_Hunk, int]:
    match = _HUNK.match(lines[i])
    if not match:
        raise PortError(f"line {i + 1}: malformed hunk header {lines[i].rstrip()!r}")
    old_start = int(match.group(1))
    old_count = int(match.group(2)) if match.group(2) is not None else 1
    new_count = int(match.group(4)) if match.group(4) is not None else 1
    hunk = _Hunk(old_start, old_count, [], [])
    i += 1
    previous = None
    while len(hunk.old) < old_count or len(hunk.new) < new_count:
        if i >= len(lines) or lines[i][:1] not in (" ", "-", "+", "\\"):
            raise PortError(
                f"line {i + 1}: hunk at -{old_start} ends before its declared "
                f"{old_count} old and {new_count} new lines"
            )
        tag, body = lines[i][:1], lines[i][1:]
        if tag == "\\":
            _no_newline(hunk, previous)
        else:
            if tag in (" ", "-"):
                hunk.old.append(body)
            if tag in (" ", "+"):
                hunk.new.append(body)
            previous = tag
        if len(hunk.old) > old_count or len(hunk.new) > new_count:
            raise PortError(f"line {i + 1}: hunk at -{old_start} exceeds its declared counts")
        i += 1
    if i < len(lines) and lines[i].startswith("\\"):  # "\ No newline at end of file"
        _no_newline(hunk, previous)
        i += 1
    return hunk, i


def _no_newline(hunk: _Hunk, previous: str | None) -> None:
    """``\\ No newline at end of file`` ends the previous line without one."""
    blocks = {" ": (hunk.old, hunk.new), "-": (hunk.old,), "+": (hunk.new,)}.get(previous or "", ())
    for block in blocks:
        block[-1] = block[-1].rstrip("\n")


def _apply_hunks(name: str, lines: list[str], hunks: list[_Hunk]) -> list[str]:
    """Apply *hunks* in order, each where its exact old lines stand nearest to
    where the patch expects them; a hunk with no old lines inserts after its
    old start line."""
    offset = 0
    for hunk in hunks:
        if hunk.old:
            expected = hunk.old_start - 1 + offset
            candidates = [
                at for at in range(len(lines) - len(hunk.old) + 1)
                if lines[at : at + len(hunk.old)] == hunk.old
            ]
            if not candidates:
                raise PortError(f"{name}: hunk at line {hunk.old_start} does not apply")
            at = min(candidates, key=lambda c: abs(c - expected))
            offset = at - (hunk.old_start - 1)
        else:
            at = hunk.old_start + offset
            if not 0 <= at <= len(lines):
                raise PortError(f"{name}: insertion after line {hunk.old_start} is out of range")
        lines[at : at + len(hunk.old)] = hunk.new
        offset += len(hunk.new) - len(hunk.old)
    return lines


def _inside(tree: Path, relative: str, patch: Path) -> Path:
    """``tree / relative``, refusing absolute paths, parent traversal and
    symlinks that lead out of *tree*."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PortError(f"{patch}: path {relative!r} is not relative to the patched tree")
    target = tree / path
    if not target.resolve().is_relative_to(tree.resolve()):
        raise PortError(f"{patch}: path {relative!r} leads out of the patched tree")
    return target


def apply_patch(tree: Path, patch: Path) -> None:
    """Apply ``patch`` to ``tree`` with exact context, or raise :class:`PortError`
    having changed nothing: every file's result is computed and checked before
    any is written."""
    try:
        files = _parse_patch(patch.read_text())
    except PortError as error:
        raise PortError(f"{patch}: {error}") from None
    results: dict[Path, str | None] = {}  # None deletes the file

    def current(path: Path) -> str | None:
        if path in results:
            return results[path]
        return path.read_text() if path.is_file() else None

    for old, new, hunks in files:
        if old is None:
            target = _inside(tree, new, patch)
            if current(target) is not None or target.exists():
                raise PortError(f"{patch}: {new} already exists")
            if any(hunk.old for hunk in hunks):
                raise PortError(f"{patch}: {new} is created from lines it does not have")
            results[target] = "".join(_apply_hunks(f"{patch.name}: {new}", [], hunks))
            continue
        source = _inside(tree, old, patch)
        text = current(source)
        if text is None:
            raise PortError(f"{patch}: {old} does not exist")
        try:
            lines = _apply_hunks(old, text.splitlines(keepends=True), hunks)
        except PortError as error:
            raise PortError(f"{patch}: {error}") from None
        if new is None:
            if lines:
                raise PortError(f"{patch}: deleting {old} would leave content behind")
            results[source] = None
            continue
        target = _inside(tree, new, patch)
        if target != source:
            results[source] = None
        results[target] = "".join(lines)

    for path, text in results.items():
        if text is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)


def defect_patches(benchmark_root: Path) -> list[Path]:
    """Each Known Defect's patch, in manifest order; every listed defect needs one."""
    manifest = benchmark_root / "data/known_defects.json"
    if not manifest.is_file():
        return []
    ids = [defect["id"] for defect in json.loads(manifest.read_text())["defects"]]
    patches = [benchmark_root / DEFECT_PATCHES / f"{defect_id}.patch" for defect_id in ids]
    missing = [str(p) for p in patches if not p.is_file()]
    if missing:
        raise PortError(f"Known Defects without a patch: {missing}")
    stray = sorted(
        p.name for p in (benchmark_root / DEFECT_PATCHES).glob("*.patch") if p.stem not in ids
    ) if (benchmark_root / DEFECT_PATCHES).is_dir() else []
    if stray:
        raise PortError(f"patches for no listed Known Defect: {stray}")
    return patches


# ---------------------------------------------------------------------------
# Porting
# ---------------------------------------------------------------------------


def _replace(source: Path, destination: Path) -> None:
    if destination.is_dir() and not destination.is_symlink():
        shutil.rmtree(destination)
    elif destination.exists() or destination.is_symlink():
        destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, ignore=_IGNORE)
    else:
        shutil.copy2(source, destination)


def _copy_known_best_workspace(known_best: Path, tree: Path) -> None:
    workspace = known_best / "workspace"
    for item in WORKSPACE_ITEMS:
        _replace(workspace / item, tree / item)
    # The cards/ package files are owned as a set: one Known-Best removed or
    # renamed is removed here too. Card directories are left alone.
    package_files = {p.name for p in (workspace / "cards").iterdir() if p.is_file()}
    if (tree / "cards").is_dir():
        for stale in sorted(p for p in (tree / "cards").iterdir() if p.is_file()):
            if stale.name not in package_files:
                stale.unlink()
    for name in sorted(package_files):
        _replace(workspace / "cards" / name, tree / "cards" / name)


def _stub_targets(workspace: Path, cards: tuple[str, ...]) -> None:
    for card in cards:
        card_dir = workspace / "cards" / card.split("_", 1)[0] / card
        if not (card_dir / "card_spec.json").is_file():
            raise PortError(f"target {card} has no Card Spec at {card_dir}")
        (card_dir / "card_impl.py").write_text(render(card_dir, make_stub=True))
        (card_dir / "tests.py").unlink(missing_ok=True)


def _mirror_oracle(benchmark_root: Path) -> None:
    workspace, oracle = benchmark_root / "workspace", benchmark_root / ORACLE
    for item in ("AGENTS.md", "skills"):
        if (workspace / item).exists():
            _replace(workspace / item, oracle / item)
        elif (oracle / item).is_dir() and not (oracle / item).is_symlink():
            shutil.rmtree(oracle / item)
        elif (oracle / item).exists() or (oracle / item).is_symlink():
            (oracle / item).unlink()
    audited = benchmark_root / "data/tests/audited"
    mirror = oracle / "tests/audited"
    if mirror.exists():
        shutil.rmtree(mirror)
    for suite in sorted(audited.rglob("tests.py")):
        if any(part in _CACHES for part in suite.parts):
            continue
        relative = suite.relative_to(audited)
        (mirror / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(suite, mirror / relative)


def _build(benchmark_root: Path, known_best: Path) -> None:
    """Port ``known_best`` into ``benchmark_root`` in place, rewriting only the
    ported paths; stops at the first error, so it runs only on a staged copy."""
    layout = load_layout(benchmark_root.parents[1], benchmark_root.name, require_cards=True)
    workspace, oracle = benchmark_root / "workspace", benchmark_root / ORACLE
    patches = defect_patches(benchmark_root)

    for tree in (workspace, oracle):
        _copy_known_best_workspace(known_best, tree)
    for suite in AUDITED_ITEMS:
        _replace(known_best / "data/tests/audited" / suite, benchmark_root / "data/tests/audited" / suite)
    _replace(known_best / "data/tests/audited/engine", workspace / "engine_tests")

    _stub_targets(workspace, layout.cards)
    for patch in patches:
        apply_patch(workspace, patch)
    if (benchmark_root / ORACLE_PATCHES).is_dir():
        for patch in sorted((benchmark_root / ORACLE_PATCHES).glob("*.patch")):
            apply_patch(oracle, patch)
    _mirror_oracle(benchmark_root)


def _differences(left: Path, right: Path, relative: Path = Path()) -> list[str]:
    compared = filecmp.dircmp(left, right, ignore=list(_CACHES))
    found = [str(relative / name) for name in compared.left_only + compared.right_only + compared.funny_files]
    _, mismatch, errors = filecmp.cmpfiles(left, right, compared.common_files, shallow=False)
    found += [str(relative / name) for name in mismatch + errors]
    for sub in compared.common_dirs:
        found += _differences(left / sub, right / sub, relative / sub)
    return found


@contextmanager
def _staged(benchmark_root: Path, known_best: Path) -> Iterator[Path]:
    """A ported copy of ``benchmark_root``, built whole before anything is
    published, so a failing step leaves the benchmark untouched."""
    with tempfile.TemporaryDirectory(prefix="port_") as tmp:
        copy = Path(tmp) / "benchmarks" / benchmark_root.name
        shutil.copytree(benchmark_root, copy, ignore=_IGNORE)
        _build(copy, known_best)
        yield copy


def port(benchmark_root: Path, known_best: Path = KNOWN_BEST) -> None:
    """Port ``known_best`` into ``benchmark_root``, rewriting only the ported
    paths, or raise :class:`PortError` having changed nothing."""
    with _staged(benchmark_root, known_best) as staged:
        for relative in _differences(benchmark_root, staged):
            source, destination = staged / relative, benchmark_root / relative
            if source.exists():
                _replace(source, destination)
            elif destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
            else:
                destination.unlink()


def check(benchmark_root: Path, known_best: Path = KNOWN_BEST) -> list[str]:
    """The paths porting would change in ``benchmark_root``; ``[]`` when it is up to date."""
    with _staged(benchmark_root, known_best) as staged:
        return sorted(_differences(benchmark_root, staged))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="report what porting would change, change nothing")
    parser.add_argument("benchmark", help="directory name under benchmarks/")
    args = parser.parse_args()
    benchmark_root = ROOT / "benchmarks" / args.benchmark
    if not (benchmark_root / "config.json").is_file():
        parser.error(f"no benchmark at {benchmark_root}")
    try:
        if args.check:
            changed = check(benchmark_root)
            for path in changed:
                print(f"would change: {path}")
            return 1 if changed else 0
        port(benchmark_root)
    except PortError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
