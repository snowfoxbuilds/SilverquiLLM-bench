"""Card implementation for Grow from the Ashes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.card_queries import choose_object
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GrowFromTheAshes(Sorcery):
    """Grow from the Ashes — {2}{G} — Sorcery.

    Kicker {2}
    Search your library for a basic land card, put it onto the
    battlefield, then shuffle. If this spell was kicked, instead search
    your library for two basic land cards, put them onto the battlefield,
    then shuffle.

    FDN collector number 225.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grow from the Ashes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {2}\nSearch your library for a basic land card, put it "
            "onto the battlefield, then shuffle. If this spell was kicked, "
            "instead search your library for two basic land cards, put them "
            "onto the battlefield, then shuffle.",
        )
        super().__init__(**kwargs)
        self.kicked: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Search for 1 (or 2 if kicked) basic land(s) and put onto battlefield."""
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        count = 2 if self.kicked else 1
        library = controller.zones[Zone.LIBRARY]

        for _ in range(count):
            # Find basic lands in library
            basics: list[Any] = []
            for card in library.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.LAND in card_types:
                    from engine.types import Supertype
                    supertypes = getattr(card, "supertypes", set())
                    if Supertype.BASIC in supertypes:
                        basics.append(card)

            if not basics:
                break

            try:
                chosen = choose_object(game, controller, basics, "basic land to search for", source_card=self)
            except Exception:
                chosen = basics[0]

            if chosen is not None:
                chosen.controller = controller
                move_to_zone(game, chosen, Zone.LIBRARY, Zone.BATTLEFIELD)

        # Shuffle library
        library.shuffle()
