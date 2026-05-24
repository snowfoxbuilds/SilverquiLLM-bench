"""Card implementation for Gutless Plunderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GutlessPlunderer(Creature):
    """Gutless Plunderer — {2}{B} — 2/2 — Skeleton Pirate — Deathtouch.

    Raid — When this creature enters, if you attacked this turn, look at
    the top three cards of your library. You may put one of those cards
    back on top of your library. Put the rest into your graveyard.

    FDN collector number 60.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gutless Plunderer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Skeleton", "Pirate"})
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Deathtouch\nRaid — When this creature enters, if you attacked "
            "this turn, look at the top three cards of your library. You may "
            "put one of those cards back on top of your library. Put the rest "
            "into your graveyard.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB with Raid: look at top 3, keep one on top, rest to graveyard."""
        from benchmarks.sos.workspace.engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # Check raid condition
        # ENGINE LIMITATION: no attacked_this_turn tracking; always triggers
        attacked = getattr(controller, "attacked_this_turn", False)
        if not attacked:
            return

        library = controller.zones[Zone.LIBRARY]
        cards = library.get_all()
        top_three = cards[-3:] if len(cards) >= 3 else cards[:]

        if not top_three:
            return

        # Choose one to keep on top (optional)
        try:
            chosen = controller.choose_card(top_three, "card to keep on top of library")
        except Exception:
            chosen = top_three[0] if top_three else None

        # Move the rest to graveyard
        for card in top_three:
            if card is chosen:
                continue
            move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
