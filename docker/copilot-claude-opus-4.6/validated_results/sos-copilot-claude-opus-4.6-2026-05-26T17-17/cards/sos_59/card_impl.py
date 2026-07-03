"""Card implementation for Matterbending Mage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MatterbendingMage(Creature):
    """Matterbending Mage — {2}{U} — Creature — Human Wizard — 2/2.

    When this creature enters, return up to one other target creature to hand.
    Whenever you cast a spell with {X} in its mana cost, can't be blocked this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Matterbending Mage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._cant_be_blocked_this_turn: bool = False

    @property
    def cant_be_blocked(self) -> bool:
        return self._cant_be_blocked_this_turn

    @cant_be_blocked.setter
    def cant_be_blocked(self, value: bool) -> None:
        self._cant_be_blocked_this_turn = value

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return targeting requirements for ETB — up to one other creature."""
        self_ref = self
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    obj is not self_ref
                    and CardType.CREATURE in getattr(obj, "card_types", set())
                ),
                description="up to one other target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Return up to one other target creature to its owner's hand."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return

        target = chosen[0]
        owner = getattr(target, "owner", None)
        if owner is None:
            return

        # Move target to hand
        target.zone = Zone.HAND
        # Remove from battlefield
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                bf.remove(target)
                break
        game.get_hand(owner).add(target)

    def on_x_spell_cast(self, game: "GameState") -> None:
        """This creature can't be blocked this turn."""
        self._cant_be_blocked_this_turn = True
