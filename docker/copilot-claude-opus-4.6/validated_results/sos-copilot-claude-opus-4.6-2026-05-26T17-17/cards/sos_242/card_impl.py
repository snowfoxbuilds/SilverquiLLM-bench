"""Card implementation for Visionary's Dance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class VisionarysDance(Sorcery):
    """Visionary's Dance — {5}{U}{R} — Sorcery.

    Create two 3/3 blue and red Elemental creature tokens with flying.
    {2}, Discard this card: Look at the top two cards of your library.
    Put one of them into your hand and the other into your graveyard.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Visionary's Dance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{U}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Create two 3/3 blue and red Elemental creature tokens with flying."""
        from engine.game import create_token

        controller = self.controller or self.owner
        for _ in range(2):
            token = Creature(
                name="Elemental",
                base_power=3,
                base_toughness=3,
                subtypes={"Elemental"},
                keywords=Keyword.FLYING,
                owner=controller,
                controller=controller,
            )
            create_token(game, controller, token)

    def activate_channel(self, game: "GameState", choice: int = 0) -> None:
        """Activated ability from hand: {2}, Discard this card.

        Look at top two cards of library. Put one into hand, other into graveyard.
        """
        controller = self.controller or self.owner

        # Discard this card (move from hand to graveyard)
        hand = controller.zones[Zone.HAND]
        if hand.contains(self):
            hand.remove(self)
            controller.zones[Zone.GRAVEYARD].add(self)

        # Look at top two cards of library
        library = controller.zones[Zone.LIBRARY]
        top_cards = library.top(2)

        if len(top_cards) == 0:
            return

        if len(top_cards) == 1:
            # Only one card - put it in hand
            library.remove(top_cards[0])
            controller.zones[Zone.HAND].add(top_cards[0])
            return

        # Two cards: choice determines which goes to hand
        to_hand = top_cards[choice]
        to_grave = top_cards[1 - choice]

        library.remove(to_hand)
        library.remove(to_grave)
        controller.zones[Zone.HAND].add(to_hand)
        controller.zones[Zone.GRAVEYARD].add(to_grave)
