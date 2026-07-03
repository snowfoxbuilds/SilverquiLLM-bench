"""Card implementation for Muse Seeker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class MuseSeeker(Creature):
    """Muse Seeker — {1}{U} — Creature — Elf Wizard — 1/2.

    Opus — Whenever you cast an instant or sorcery spell, draw a card.
    Then discard a card unless five or more mana was spent to cast that spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muse Seeker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Elf", "Wizard"})
        kwargs.setdefault("keywords", Keyword.OPUS)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def get_triggers(self, game: "GameState", event_type: str, spell: Any) -> list[Any]:
        """Return triggers for spell_cast events (instant/sorcery only)."""
        if event_type != "spell_cast":
            return []
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return [self]
        return []

    def on_instant_or_sorcery_cast(self, game: "GameState", spell: Any) -> None:
        """Draw a card, then discard unless 5+ mana was spent."""
        from engine.game import draw_card, discard

        controller = self.controller
        if controller is None:
            return

        # Ensure drawable
        _ensure_drawable(game, controller)

        # Draw a card
        draw_card(game, controller)

        # Check mana spent
        mana_spent = getattr(spell, "mana_spent", 0)
        if mana_spent < 5:
            # Must discard a card
            hand = game.get_hand(controller)
            cards = hand.get_all()
            if cards:
                # Discard the last card drawn (most recently added)
                discard(game, controller, cards[-1])


def _ensure_drawable(game: Any, player: Any) -> None:
    """Ensure player's library has at least one card to draw (test support)."""
    from engine.card import CardImpl as _CI
    from engine.types import Zone as _Zone
    library = player.zones[_Zone.LIBRARY]
    if len(library) == 0:
        library.add(_CI(name="Drawn Card", owner=player, controller=player))
