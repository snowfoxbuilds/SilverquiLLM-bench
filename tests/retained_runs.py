"""Simulated benchmark runs built once per module and cloned into each test that changes them.

A simulated benchmark runs the whole ``run_benchmark`` pipeline and costs seconds, so a module
builds its runs once and each test works on a clone of them (see
docs/specs/TESTING-CONVENTIONS.md). Records, login journals and plugin environments name their
own files by absolute path, so a clone rewrites the template's root to its own in each text file.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from . import unit_environment
from .grader_fixtures import local_grader
from .test_karn_execution import FixtureHost, options


@contextlib.contextmanager
def building():
    """The unit-test environment for a module-scoped fixture, which autouse fixtures do not reach."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        unit_environment.apply(monkeypatch)
        yield monkeypatch


def clone_tree(template: Path, destination: Path) -> Path:
    """Copy ``template`` to ``destination`` (absent or empty), rewriting the template's root in
    every text file that names it; binary files, such as compiled modules, are copied as they are."""
    shutil.copytree(template, destination, symlinks=True, dirs_exist_ok=True)
    old, new = str(template).encode(), str(destination).encode()
    for path in destination.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        if old in data and b"\0" not in data:
            path.write_bytes(data.replace(old, new))
    return destination


def rebase_options(opts: dict, template: Path, destination: Path, **fresh) -> dict:
    """The template's run options pointed at a clone, with a fresh host and grader."""
    rebased = {}
    for key, value in opts.items():
        if isinstance(value, Path) and value.is_relative_to(template):
            value = destination / value.relative_to(template)
        rebased[key] = value
    rebased["host"] = fresh.pop("host", None) or FixtureHost()
    rebased["grader"] = fresh.pop("grader", None) or local_grader()
    return {**rebased, **fresh}


def clone(template: SimpleNamespace, directory: Path, **fresh) -> SimpleNamespace:
    """A copy of a built template under ``directory``: its ``root`` tree and ``opts`` follow the copy;
    every other attribute (records, summaries) is the template's own, read-only."""
    root = clone_tree(template.root, directory / template.root.name)
    return SimpleNamespace(
        **{
            **vars(template),
            "root": root,
            "opts": rebase_options(template.opts, template.root, root, **fresh),
        }
    )


def build_plain_run(root: Path) -> SimpleNamespace:
    """One successful simulated benchmark of the toy ``example`` benchmark."""
    from silverquillm.karn.execution import run_benchmark

    opts = options(root)
    with building():
        record = run_benchmark(**opts)
    return SimpleNamespace(root=root, opts=opts, record=record)
