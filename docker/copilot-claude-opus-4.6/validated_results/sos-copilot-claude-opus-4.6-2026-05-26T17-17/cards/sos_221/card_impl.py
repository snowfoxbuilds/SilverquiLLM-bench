"""Card implementation for Resonating Lute."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import Artifact
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


@dataclass
class GrantedManaAbility:
    """A granted mana ability with amount and spend restriction."""
    mana_amount: int = 2
    spend_restriction: str | None = "instant_and_sorcery"
    description: str = ""


class ResonatingLute(Artifact):
    """Resonating Lute — {2}{U}{R} — Artifact.

    Lands you control have "{T}: Add two mana of any one color. Spend this
    mana only to cast instant and sorcery spells."
    {T}: Draw a card. Activate only if you have seven or more cards in your hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Resonating Lute")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            'Lands you control have "{T}: Add two mana of any one color. '
            'Spend this mana only to cast instant and sorcery spells."\n'
            "{T}: Draw a card. Activate only if you have seven or more cards in your hand.",
        )
        super().__init__(**kwargs)

    def get_granted_abilities(self, game: "GameState", target: Any) -> list[GrantedManaAbility]:
        """Return mana abilities granted to a land controlled by the same player."""
        # Only grant to lands we control
        if CardType.LAND not in getattr(target, "card_types", set()):
            return []
        if getattr(target, "controller", None) != self.controller:
            return []
        return [GrantedManaAbility(
            mana_amount=2,
            spend_restriction="instant_and_sorcery",
            description="{T}: Add two mana of any one color. Spend this mana only to cast instant and sorcery spells.",
        )]

    def can_activate_draw(self, game: "GameState") -> bool:
        """Return True if the draw ability can be activated (7+ cards in hand)."""
        controller = self.controller
        if controller is None:
            return False
        hand = game.get_hand(controller)
        return len(hand) >= 7

    def activate_draw(self, game: "GameState") -> None:
        """Activate: {T}: Draw a card."""
        self.is_tapped = True
        controller = self.controller
        if controller is None:
            return
        from engine.game import draw_card
        draw_card(game, controller)
