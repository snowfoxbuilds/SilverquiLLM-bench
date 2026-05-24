"""Card implementation for Raise the Past."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RaiseThePast(Sorcery):
    """Raise the Past — {2}{W}{W} — Sorcery.

    Return all creature cards with mana value 2 or less from your
    graveyard to the battlefield.

    FDN collector number 22.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Raise the Past")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Return all creature cards with mana value 2 or less from "
            "your graveyard to the battlefield.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Return all creature cards with mana value <= 2 from graveyard
        to the battlefield."""
        from benchmarks.sos.workspace.engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        graveyard = controller.zones[Zone.GRAVEYARD]
        # Snapshot to avoid mutation during iteration
        to_return: list[Any] = []
        for card in list(graveyard.get_all()):
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                continue
            mc = getattr(card, "mana_cost", None)
            if mc is None:
                # Cards with no mana cost have mana value 0
                to_return.append(card)
                continue
            if mc.cmc <= 2:
                to_return.append(card)

        for card in to_return:
            card.controller = controller
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)
