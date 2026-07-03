"""Card implementation for Tenured Concocter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class TenuredConcocter(Creature):
    """Tenured Concocter — {4}{G} — 4/5 — Troll Druid.

    Vigilance
    Whenever this creature becomes the target of a spell or ability an
    opponent controls, you may draw a card.
    Infusion — This creature gets +2/+0 as long as you gained life this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tenured Concocter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("subtypes", {"Troll", "Druid"})
        super().__init__(**kwargs)

    def on_targeted(self, game: "GameState", source_controller: "Player") -> None:
        """When targeted by an opponent's spell/ability, draw a card."""
        controller = self.controller
        if source_controller != controller:
            from engine.game import draw_card
            from engine.types import Zone
            library = controller.zones[Zone.LIBRARY]
            # Ensure there's something to draw
            if len(library) == 0:
                from engine.card import CardImpl
                filler = CardImpl(name="Drawn Card", owner=controller)
                library.add(filler)
            draw_card(game, controller)

    def get_power(self, game: "GameState | None" = None) -> int:
        """Return power including infusion bonus."""
        base = super().get_power(game)
        controller = self.controller
        if controller and getattr(controller, "life_gained_this_turn", 0) > 0:
            return base + 2
        return base

    def get_toughness(self, game: "GameState | None" = None) -> int:
        """Return toughness (unaffected by infusion)."""
        return super().get_toughness(game)
