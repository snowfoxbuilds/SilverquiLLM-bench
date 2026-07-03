"""Card implementation for Zealous Lorecaster."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ZealousLorecaster(Creature):
    """Zealous Lorecaster — {5}{R} — Creature — Giant Sorcerer — 4/4.

    When this creature enters, return target instant or sorcery card from
    your graveyard to your hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zealous Lorecaster")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Giant", "Sorcerer"})
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target instant or sorcery card "
            "from your graveyard to your hand.",
        )
        super().__init__(**kwargs)

    def get_etb_targets(self, game: "GameState") -> list[Any]:
        """Target instant or sorcery card in your graveyard."""
        controller = self.controller

        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target instant or sorcery card from your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_enter_battlefield(self, game: "GameState") -> None:
        """ETB: return target instant or sorcery from graveyard to hand."""
        controller = self.controller
        if controller is None:
            return

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target = chosen[0]
        gy = game.get_graveyard(controller)
        hand = game.get_hand(controller)

        if gy.contains(target):
            gy.remove(target)
            hand.add(target)
