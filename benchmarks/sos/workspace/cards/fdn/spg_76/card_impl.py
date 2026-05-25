"""Card implementation for Grim Tutor."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class GrimTutor(Sorcery):
    """Grim Tutor — {1}{B}{B} — Sorcery

    Search your library for a card, put that card into your hand, then
    shuffle your library. You lose 3 life.

    SPG collector number 76.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grim Tutor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Search your library for a card, put that card into your hand, "
            "then shuffle your library. You lose 3 life.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        """Resolve Grim Tutor: search library, put card in hand, shuffle, lose 3 life."""
        controller = self.controller or self.owner
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        hand = controller.zones[Zone.HAND]

        # Search: pick a card from library via player choice API,
        # or use chosen_targets if pre-set (e.g. by tests).
        chosen = getattr(self, "chosen_targets", None)
        target_card = None

        if chosen and len(chosen) > 0:
            target_card = chosen[0]
        else:
            all_cards = library.get_all()
            if all_cards:
                try:
                    target_card = controller.choose_card(
                        all_cards, "Search your library for a card"
                    )
                except Exception:
                    target_card = all_cards[0]

        if target_card is not None and library.contains(target_card):
            library.remove(target_card)
            hand.add(target_card)

        # Shuffle library
        library.shuffle()

        # Lose 3 life
        controller.life -= 3
