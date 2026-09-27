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

    def alternative_costs(self, game: "GameState") -> list[ManaCost]:
        """Offer {B} as an alternative cost when 13+ creatures are in play.

        Unlike a cost *reduction* (which only touches generic mana), an
        alternative cost fully replaces {3}{B}{B} with {B}.
        """
        total_creatures = sum(
            1
            for player in game.players
            for obj in game.get_battlefield(player).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )
        if total_creatures >= 13:
            return [ManaCost.parse("{B}")]
        return []

    def on_resolve(self, game: "GameState") -> None:
        """Each player sacrifices thirteen creatures of their choice."""
        from engine.game import sacrifice

        for player in game.players:
            bf = game.get_battlefield(player)
            for _ in range(13):
                creatures = [
                    c
                    for c in bf.get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                ]
                if not creatures:
                    break
                chosen = choose_object(
                    game, player, creatures, "sacrifice a creature", source_card=self
                )
                if chosen is not None:
                    sacrifice(game, player, chosen)
