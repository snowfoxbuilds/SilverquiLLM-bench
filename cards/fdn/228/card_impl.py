"""Card implementation for SocialSnub."""

from __future__ import annotations


from engine.card import Artifact, Creature, Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any
import math

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class SocialSnub(Sorcery):
    """Social Snub — {1}{W}{B} — Each player sacrifices a creature.
    Each opponent loses 1 life and you gain 1 life.

    The "copy if you control a creature" trigger is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Social Snub")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault(
            "rules_text",
            "When you cast this spell while you control a creature, you may "
            "copy this spell.\nEach player sacrifices a creature of their "
            "choice. Each opponent loses 1 life and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import sacrifice

        controller = self.controller
        if controller is None:
            return

        # Each player sacrifices a creature
        for player in game.players:
            creatures = [
                obj
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ]
            if creatures:
                sacrifice(game, player, creatures[0])

        # Each opponent loses 1 life, you gain 1 life
        for player in game.players:
            if player is not controller:
                player.life -= 1
                controller.life += 1


__all__ = ["SocialSnub"]
