"""Card implementation for Strongbox Raider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.card_queries import choose_object
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StrongboxRaider(Creature):
    """Strongbox Raider — {2}{R}{R} — 5/2 — Orc Pirate.

    Raid — When this creature enters, if you attacked this turn, exile
    the top two cards of your library. Choose one of them. Until the end
    of your next turn, you may play that card.

    FDN collector number 96.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Strongbox Raider")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{R}"))
        kwargs.setdefault("subtypes", {"Orc", "Pirate"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Raid — When this creature enters, if you attacked this turn, "
            "exile the top two cards of your library. Choose one of them. "
            "Until the end of your next turn, you may play that card.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: Raid — exile top 2, choose one playable until end of next turn."""
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # Check Raid
        attacked_this_turn = getattr(game, "attacked_this_turn", False)
        if not attacked_this_turn:
            combat = getattr(game, "combat", None)
            if combat is not None:
                attackers = getattr(combat, "attackers", [])
                for attacker in attackers:
                    if getattr(attacker, "controller", None) is controller:
                        attacked_this_turn = True
                        break
        if not attacked_this_turn:
            attacked_this_turn = getattr(controller, "attacked_this_turn", False)

        if not attacked_this_turn:
            return

        # Exile top two cards
        library = controller.zones[Zone.LIBRARY]
        cards = list(library.get_all())
        if not cards:
            return

        top_cards = cards[-2:] if len(cards) >= 2 else cards[-1:]
        exiled: list = []
        for card in top_cards:
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)

        if not exiled:
            return

        # Choose one
        try:
            chosen = choose_object(game, controller, exiled, "card to play until end of next turn", source_card=self)
        except Exception:
            chosen = exiled[0]

        if chosen is not None:
            # ENGINE LIMITATION: "You may play that card until end of your
            # next turn" not fully implementable without play-permission system.
            chosen._playable_until_next_turn = True
