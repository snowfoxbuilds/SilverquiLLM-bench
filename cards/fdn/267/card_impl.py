from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype


class SecludedCourtyard(Land):
    """Secluded Courtyard."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Secluded Courtyard")
        super().__init__(**kwargs)
