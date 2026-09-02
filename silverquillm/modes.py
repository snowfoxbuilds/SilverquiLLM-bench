"""Benchmark Mode registry.

A *Benchmark Mode* is a bench-side run-spec parameter that varies how the
synthetic task is synthesized.  It is orthogonal to the candidate and the
benchmark, never part of candidate identity, and never encoded in an image
name.  The registry is in-code (not filesystem-discovered) so the set of
runnable modes is fixed and auditable.

Per the Bench Contract (``docs/specs/BENCH-CONTRACT.md``), the scaffolding
prompt always comes from TheOzolith's production renderer
(:func:`theozolith_worker.api.render_run_prompt`) — a hand-rolled template
would drift silently as the production prompt evolves.  A Benchmark Mode may
therefore vary only the *synthetic issue* the renderer wraps (task synthesis),
never the prompt scaffolding and never the substrate's execution ``mode``.

The substrate's execution mode (``run`` / ``review``) is a different concept
that selects the Output Proposal schema; bench implementer runs are always
``mode: run`` (BENCH-CONTRACT.md).  Reviewer runs are deferred (#39).

Public API
----------
- :class:`BenchmarkMode` — a frozen mode descriptor.
- :data:`MODES` — the registry (``basic``, ``planned``).
- :func:`get_mode` — look up a mode by name, failing loud on the unknown.
- :class:`UnknownModeError` — raised for an unregistered mode name.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "MODES",
    "BenchmarkMode",
    "UnknownModeError",
    "get_mode",
]

#: Constant driver reference stamped by every bench-driven mode.  The bench is
#: one driver; the mode does not select a different one.
DRIVER_REF = "bench:jobdir-v1"

#: Constant evaluation method: every bench run is scored by the Audited Eval.
EVALUATION_METHOD = "audited_eval"

#: The ``planned`` mode's task-synthesis variation: a plan-first clause appended
#: to the synthetic issue body.  The production renderer wraps it unchanged.
_PLANNED_ADDENDUM = (
    "\n\n## Approach\n\n"
    "Before implementing, write a short plan: list the target cards, the engine "
    "primitives each one needs, and the order you will implement them. Then "
    "execute that plan."
)


class UnknownModeError(Exception):
    """Raised when a mode name is not in :data:`MODES`."""


@dataclass(frozen=True)
class BenchmarkMode:
    """A Benchmark Mode: a name plus its task-synthesis variation.

    ``issue_addendum`` is appended to the synthetic issue body the production
    prompt renderer wraps (empty for no change).  ``basic`` and ``planned``
    differ only in that addendum — same driver, same evaluation method, same
    production prompt scaffolding, same proposal contract.
    """

    name: str
    issue_addendum: str = ""
    driver_ref: str = DRIVER_REF
    evaluation_method: str = EVALUATION_METHOD


MODES: dict[str, BenchmarkMode] = {
    "basic": BenchmarkMode(name="basic"),
    "planned": BenchmarkMode(name="planned", issue_addendum=_PLANNED_ADDENDUM),
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
