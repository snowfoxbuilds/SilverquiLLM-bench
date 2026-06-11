"""Card implementation for Artistic Process."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ArtisticProcess(Sorcery):
    """Artistic Process — {3}{R}{R} — Sorcery.

    Choose one —
    • Artistic Process deals 6 damage to target creature.
    • Artistic Process deals 2 damage to each creature you don't control.
    • Create a 3/3 blue and red Elemental creature token with flying and haste.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Artistic Process")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{R}"))
        super().__init__(**kwargs)
        self.chosen_mode: int = 1

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner

        if self.chosen_mode == 1:
            chosen = getattr(self, "chosen_targets", None)
            target = chosen[0] if chosen else None
            if target is not None:
                from engine.game import deal_damage
                deal_damage(game, self, target, 6)

        elif self.chosen_mode == 2:
            from engine.game import deal_damage
            for player in game.players:
                if player is controller:
                    continue
                bf = game.get_battlefield(player)
                creatures = [c for c in bf if CardType.CREATURE in getattr(c, "card_types", set())]
                for creature in creatures:
                    deal_damage(game, self, creature, 2)

        elif self.chosen_mode == 3:
            from engine.game import create_token
            token = Creature(
                name="Elemental",
                subtypes={"Elemental"},
                base_power=3,
                base_toughness=3,
                keywords=Keyword.FLYING | Keyword.HASTE,
            )
            create_token(game, controller, token)
