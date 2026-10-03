"""Simulated benchmark runs built once per module and cloned into each test that changes them.

A simulated benchmark runs the whole ``run_benchmark`` pipeline and costs seconds, so a module
builds its runs once and each test works on a byte-for-byte clone of them (see
docs/specs/TESTING-CONVENTIONS.md). Records name their own artifacts by absolute path, so a
clone rewrites the template's root to its own inside the JSON it carries.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import pytest

from . import unit_environment
from .grader_fixtures import local_grader
from .test_karn_execution import FixtureHost


@contextlib.contextmanager
def building():
    """The unit-test environment for a module-scoped fixture, which autouse fixtures do not reach."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        unit_environment.apply(monkeypatch)
        yield monkeypatch


def clone_tree(template: Path, destination: Path) -> Path:
    shutil.copytree(template, destination, symlinks=True)
    old, new = str(template), str(destination)
    for path in destination.rglob("*.json"):
        if path.is_file() and not path.is_symlink():
            text = path.read_text()
            if old in text:
                path.write_text(text.replace(old, new))
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
