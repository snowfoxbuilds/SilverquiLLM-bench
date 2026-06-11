"""Card implementation for Group Project."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery, Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class GroupProject(Sorcery):
    """Group Project — {1}{W} — Sorcery.

    Create a 2/2 red and white Spirit creature token.
    Flashback—Tap three untapped creatures you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Group Project")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 2/2 red and white Spirit creature token.\n"
            "Flashback—Tap three untapped creatures you control.",
        )
        super().__init__(**kwargs)
        self.has_flashback = True

    def on_resolve(self, game: "GameState") -> None:
        """Create a 2/2 red and white Spirit creature token."""
        from engine.game import create_token

        controller = getattr(self, "controller", None)
        if controller is None:
            return

        token = Creature(
            name="Spirit",
            base_power=2,
            base_toughness=2,
            subtypes={"Spirit"},
            owner=controller,
            controller=controller,
        )
        token.colors = {"W", "R"}
        create_token(game, controller, token)

    def cast_flashback(self, game: "GameState", player: "Player") -> None:
        """Cast from graveyard by tapping three untapped creatures."""
        from engine.game import create_token
        from engine.stack import StackObject

        # Pay cost: tap three untapped creatures
        bf = game.get_battlefield(player).get_all()
        untapped_creatures = [
            c for c in bf
            if CardType.CREATURE in getattr(c, "card_types", set())
            and not getattr(c, "is_tapped", True)
        ]
        if len(untapped_creatures) < 3:
            raise Exception("Not enough untapped creatures for flashback cost")

        for c in untapped_creatures[:3]:
            c.is_tapped = True

        # Remove from graveyard
        graveyard = game.get_graveyard(player)
        graveyard.remove(self)

        # Mark as flashback cast for exile on resolution
        self._cast_via_flashback = True
        self.controller = player

        # Push to stack
        card = self

        def _on_resolve(g: "GameState") -> None:
            card.on_resolve(g)
            # Exile after flashback resolution
            player.zones[Zone.EXILE].add(card)

        stack_obj = StackObject(
            source=self,
            controller=player,
            on_resolve=_on_resolve,
        )
        game.stack.push(stack_obj)

