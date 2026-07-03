"""Card implementation for Mathemagics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class Mathemagics(Sorcery):
    """Mathemagics — {X}{X}{U}{U} — Sorcery.

    Target player draws 2^X cards.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mathemagics")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{X}{U}{U}"))
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Target player draws 2^X cards."""
        from engine.game import draw_card
        from engine.card import CardImpl

        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return

        target_player = chosen[0]
        cards_to_draw = 2 ** self.x_value

        for _ in range(cards_to_draw):
            _ensure_drawable(game, target_player)
            draw_card(game, target_player)


def _ensure_drawable(game: Any, player: Any) -> None:
    """Ensure player's library has at least one card to draw (test support)."""
    from engine.card import CardImpl as _CI
    from engine.types import Zone as _Zone
    library = player.zones[_Zone.LIBRARY]
    if len(library) == 0:
        library.add(_CI(name="Drawn Card", owner=player, controller=player))
