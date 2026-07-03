"""Card implementation for Social Snub."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SocialSnub(Sorcery):
    """Social Snub — {1}{W}{B} — Sorcery.

    When you cast this spell while you control a creature, you may copy this spell.
    Each player sacrifices a creature of their choice.
    Each opponent loses 1 life and you gain 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Social Snub")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        super().__init__(**kwargs)
        self._should_copy: bool = False

    def on_cast(self, game: "GameState") -> None:
        """When cast while controlling a creature, mark for copy."""
        controller = self.controller
        if controller is None:
            return
        bf = game.get_battlefield(controller)
        creatures = [
            obj for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        ]
        # Copy if controller has enough creatures to sacrifice for both
        # resolutions (original + copy each need a sacrifice target)
        self._should_copy = len(creatures) >= 2

    def on_resolve(self, game: "GameState") -> None:
        """Each player sacrifices a creature. Each opponent loses 1, you gain 1."""
        # If copied, resolve copy first (copy on top of stack resolves first)
        if self._should_copy:
            self._should_copy = False
            self._resolve_effect(game)

        self._resolve_effect(game)

    def _resolve_effect(self, game: "GameState") -> None:
        """Single resolution: each player sacs a creature, drain 1."""
        controller = self.controller

        # Each player sacrifices a creature of their choice
        for player in game.players:
            bf = game.get_battlefield(player)
            creatures = [
                obj for obj in bf.get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ]
            if creatures:
                victim = creatures[0]
                bf.remove(victim)
                game.get_graveyard(player).add(victim)

        # Each opponent loses 1 life, controller gains 1 life
        if controller is not None:
            for player in game.players:
                if player is not controller:
                    player.life -= 1
            controller.life += 1
