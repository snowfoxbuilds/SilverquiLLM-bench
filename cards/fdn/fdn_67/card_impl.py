"""Card implementation for Revenge of the Rats."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RevengeOfTheRats(Sorcery):
    """Revenge of the Rats — {2}{B}{B} — Sorcery.

    Create a tapped 1/1 black Rat creature token for each creature card
    in your graveyard.
    Flashback {2}{B}{B}

    FDN collector number 67.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Revenge of the Rats")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Create a tapped 1/1 black Rat creature token for each creature "
            "card in your graveyard.\nFlashback {2}{B}{B}",
        )
        super().__init__(**kwargs)
        # ENGINE LIMITATION: Flashback not fully supported as mechanic
        self.flashback_cost = ManaCost.parse("{2}{B}{B}")

    def on_resolve(self, game: "GameState") -> None:
        """Create tapped Rat tokens equal to creature cards in graveyard."""
        from benchmarks.sos.workspace.engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        gy = controller.zones[Zone.GRAVEYARD]
        creature_count = sum(
            1 for c in gy.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )

        for _ in range(creature_count):
            token = Creature(
                name="Rat",
                subtypes={"Rat"},
                base_power=1,
                base_toughness=1,
            )
            create_token(game, controller, token)
            # Token enters tapped
            token.is_tapped = True
            token.tapped = True
