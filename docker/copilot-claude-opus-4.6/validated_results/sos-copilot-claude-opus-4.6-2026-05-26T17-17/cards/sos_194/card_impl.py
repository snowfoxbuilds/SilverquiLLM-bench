"""Card implementation for Hardened Academic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class _DiscardAbility:
    """Activated ability: Discard a card -> gains lifelink until end of turn."""

    def __init__(self, source: "HardenedAcademic") -> None:
        self.source = source
        self.description = "Discard a card: This creature gains lifelink until end of turn."

    def activate(self, game: "GameState", costs: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Activate: discard a card, gain lifelink."""
        if costs is None:
            return
        discard_card = costs.get("discard")
        if discard_card is None:
            return

        controller = self.source.controller
        if controller is None:
            return

        # Move discarded card to graveyard
        hand = controller.zones[Zone.HAND]
        if hand.contains(discard_card):
            hand.remove(discard_card)
        controller.zones[Zone.GRAVEYARD].add(discard_card)
        discard_card.zone = Zone.GRAVEYARD

        # Grant lifelink until end of turn
        self.source.keywords = self.source.keywords | Keyword.LIFELINK


class _GraveyardLeaveTrigger:
    """Triggered: cards leave graveyard -> +1/+1 counter on target creature."""

    def __init__(self, source: "HardenedAcademic") -> None:
        self.source = source
        self.description = "Whenever one or more cards leave your graveyard, put a +1/+1 counter on target creature you control."


class HardenedAcademic(Creature):
    """Hardened Academic — {R}{W} — Creature — Bird Cleric — 2/1.

    Flying, haste
    Discard a card: This creature gains lifelink until end of turn.
    Whenever one or more cards leave your graveyard, put a +1/+1 counter on
    target creature you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hardened Academic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("subtypes", {"Bird", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def get_activated_abilities(self, game: "GameState" = None) -> list[Any]:
        """Return the discard ability."""
        return [_DiscardAbility(self)]

    def get_triggered_abilities(self, game: "GameState") -> list[Any]:
        """Return the graveyard-leave trigger."""
        return [_GraveyardLeaveTrigger(self)]
