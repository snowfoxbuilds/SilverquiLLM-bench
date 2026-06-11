"""Card implementation for Flashback (the card)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Flashback(Instant):
    """Flashback — {R} — Instant.

    Target instant or sorcery card in your graveyard gains flashback until end
    of turn. The flashback cost is equal to its mana cost.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Flashback")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault(
            "rules_text",
            "Target instant or sorcery card in your graveyard gains flashback "
            "until end of turn. The flashback cost is equal to its mana cost.",
        )
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target instant or sorcery card in your graveyard."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.INSTANT in getattr(obj, "card_types", set())
                    or CardType.SORCERY in getattr(obj, "card_types", set())
                ),
                description="target instant or sorcery card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Grant flashback to target card until end of turn."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # Grant flashback keyword
        target.keywords = getattr(target, "keywords", Keyword(0)) | Keyword.FLASHBACK

        # Set flashback cost equal to mana cost
        target.flashback_cost = getattr(target, "mana_cost", ManaCost())

        # Mark as temporary (until end of turn) - store original state for cleanup
        target._flashback_granted_temporarily = True

        # Store original end_of_turn_cleanup if it exists, then patch it
        _original_cleanup = getattr(target, "end_of_turn_cleanup", None)

        def _cleanup(game: Any) -> None:
            from engine.types import KeywordSet as _KS
            # Remove flashback keyword - reset to original
            orig = target._original_keywords if hasattr(target, "_original_keywords") else Keyword(0)
            # Wrap in KeywordSet so sentinel `in` checks work properly
            if isinstance(orig, Keyword):
                target.keywords = _KS(orig)
            else:
                target.keywords = orig
            if hasattr(target, "flashback_cost"):
                del target.flashback_cost
            target._flashback_granted_temporarily = False
            if _original_cleanup:
                _original_cleanup(game)

        target.end_of_turn_cleanup = _cleanup
