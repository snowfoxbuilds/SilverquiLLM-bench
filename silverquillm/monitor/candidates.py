"""How the monitor names a Benchmark Candidate (RUN-MONITORING.md, Candidate display)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._read import mapping

MISSING = "—"


@dataclass(frozen=True)
class CandidateDisplay:
    name: str
    model: str
    effort: str
    hash8: str | None = None
    recipe_revision: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name} · {self.model} · {self.effort}"

    @property
    def key(self) -> tuple[str, str, str]:
        """What groups candidates: one name has been built with different models and efforts."""
        return (self.name, self.model, self.effort)

    @property
    def secondary(self) -> tuple[str, ...]:
        """Short labels for lists: the recipe revision is a full commit id, cut like hash8."""
        revision = self.recipe_revision[:8] if self.recipe_revision else None
        return tuple(label for label in (self.hash8, revision) if label)


def _text(value: Any) -> str:
    return value if isinstance(value, str) and value else MISSING


def candidate_display(
    definition: Any, candidate_hash: str | None = None, recipe_revision: str | None = None
) -> CandidateDisplay:
    """From a Construct Definition: its name and its model and effort runtime environment."""
    definition = mapping(definition)
    environment = mapping(mapping(definition.get("runtime")).get("environment"))
    return CandidateDisplay(
        _text(definition.get("name")),
        _text(environment.get("CONSTRUCT_MODEL")),
        _text(environment.get("CONSTRUCT_EFFORT")),
        candidate_hash[:8] if isinstance(candidate_hash, str) and candidate_hash else None,
        recipe_revision if isinstance(recipe_revision, str) and recipe_revision else None,
    )
