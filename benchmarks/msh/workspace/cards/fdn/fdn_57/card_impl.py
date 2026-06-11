"""Card implementation for Blasphemous Edict."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.card_queries import choose_object
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BlasphemousEdict(Sorcery):
    """Blasphemous Edict — {3}{B}{B} — Sorcery.

    You may pay {B} rather than pay this spell's mana cost if there are
    thirteen or more creatures on the battlefield.
    Each player sacrifices thirteen creatures of their choice.

    FDN collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blasphemous Edict")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "You may pay {B} rather than pay this spell's mana cost if "
            "there are thirteen or more creatures on the battlefield.\n"
            "Each player sacrifices thirteen creatures of their choice.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Allow alternative cost of {B} if 13+ creatures on battlefield.

        The alternative cost should make total cost {B}. The original cost is
        {3}{B}{B} (generic=3, pips={B:2}). cost_reduction only reduces
        the generic portion. We return 4 (intent: reduce fully to {B}),
        but the engine's get_cost_reduction() clamps to min(4, generic=3)=3,
        yielding {B}{B}. Full alternative-cost support (removing colored
        pips) would require engine changes beyond current scope.
        """
        total_creatures = 0
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    total_creatures += 1
        if total_creatures >= 13:
            return 4  # Intent: reduce to {B}; engine limitation applies
        return 0

    def on_resolve(self, game: "GameState") -> None:
        """Each player sacrifices thirteen creatures of their choice."""
        from engine.game import sacrifice

        for player in game.players:
            bf = game.get_battlefield(player)
            for _ in range(13):
                creatures = [
                    c for c in bf.get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                ]
                if not creatures:
                    break
                try:
                    chosen = choose_object(game, player, creatures, "sacrifice a creature", source_card=self)
                except Exception:
                    chosen = creatures[-1] if creatures else None
                if chosen is not None:
                    sacrifice(game, player, chosen)
