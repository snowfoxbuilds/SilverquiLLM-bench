"""Card implementation for WishclawTalisman."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class WishclawTalisman(Artifact):
    """Wishclaw Talisman — {1}{B} — Enters with 3 wish counters.
    {1}, {T}, Remove counter: Tutor a card; opponent gains control."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wishclaw Talisman")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "This artifact enters with three wish counters on it.\n"
            "{1}, {T}, Remove a wish counter from this artifact: Search your library "
            "for a card, put it into your hand, then shuffle. An opponent gains "
            "control of this artifact. Activate only during your turn.",
        )
        super().__init__(**kwargs)
        self.wish_counters: int = 3

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            if source.wish_counters <= 0:
                return False
            src.is_tapped = True
            source.wish_counters -= 1
            return True

        def _effect(game: Any) -> None:
            from engine.types import Zone
            controller = source.controller
            if controller is not None:
                # Search library for a card, put it in hand, shuffle
                library = controller.zones[Zone.LIBRARY]
                hand = controller.zones[Zone.HAND]
                all_cards = library.get_all()
                if all_cards:
                    chosen = all_cards[0]  # Simplified: pick first card
                    library.remove(chosen)
                    hand.add(chosen)
                library.shuffle()
            # ENGINE LIMITATION: control transfer to opponent not implemented

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{1}, {T}, Remove a wish counter: Tutor; opponent gains control.",
            ),
        ]


__all__ = ["WishclawTalisman"]
