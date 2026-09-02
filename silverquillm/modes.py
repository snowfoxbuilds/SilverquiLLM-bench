"""Benchmark Mode registry.

A *Benchmark Mode* selects the task-file template a Contract Run stages into
the job directory.  It is a run-spec parameter — orthogonal to the candidate
and the benchmark, never part of candidate identity, and never encoded in an
image name.  The registry is in-code (not filesystem-discovered) so the set of
runnable modes is fixed and auditable.

The substrate's execution ``mode`` (``run`` / ``review``) is a *different*
concept — it selects the Output Proposal schema.  Reviewer runs are deferred
(#39), so the bench only ever drives implementer sessions; the Benchmark Mode
here therefore only varies the task prose, never the proposal contract.

Public API
----------
- :class:`BenchmarkMode` — a frozen mode descriptor.
- :data:`MODES` — the registry (``basic``, ``planned``).
- :func:`get_mode` — look up a mode by name, failing loud on the unknown.
- :class:`UnknownModeError` — raised for an unregistered mode name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MODES",
    "BenchmarkMode",
    "UnknownModeError",
    "get_mode",
]

#: Directory holding the task-file templates a mode renders.
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

#: Constant driver reference stamped by every bench-driven mode.  The bench is
#: one driver; the mode does not select a different one.
DRIVER_REF = "bench:jobdir-v1"

#: Constant evaluation method: every bench run is scored by the Audited Eval.
EVALUATION_METHOD = "audited_eval"


class UnknownModeError(Exception):
    """Raised when a mode name is not in :data:`MODES`."""


@dataclass(frozen=True)
class BenchmarkMode:
    """A Benchmark Mode: the task template plus the constant driver/eval refs.

    ``task_template`` is the Markdown template rendered into the job dir's task
    file (``input/prompt.md``).  ``basic`` and ``planned`` differ only in that
    template — same driver, same evaluation method, same proposal contract.
    """

    name: str
    task_template: Path
    driver_ref: str = DRIVER_REF
    evaluation_method: str = EVALUATION_METHOD


MODES: dict[str, BenchmarkMode] = {
    "basic": BenchmarkMode(name="basic", task_template=TEMPLATES_DIR / "task_basic.md"),
    "planned": BenchmarkMode(name="planned", task_template=TEMPLATES_DIR / "task_planned.md"),
}


def get_mode(name: str) -> BenchmarkMode:
    """Return the :class:`BenchmarkMode` named *name*.

    Raises :class:`UnknownModeError` — listing the registered modes — for any
    name not in :data:`MODES`.
    """
    try:
        return MODES[name]
    except KeyError:
        registered = ", ".join(sorted(MODES))
        raise UnknownModeError(
            f"unknown benchmark mode {name!r}; registered modes: {registered}"
        ) from None
