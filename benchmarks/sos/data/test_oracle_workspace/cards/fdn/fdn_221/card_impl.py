"""Card implementation for Genesis Wave."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# Permanent card types for Genesis Wave
_PERMANENT_TYPES = {
    CardType.CREATURE, CardType.ENCHANTMENT, CardType.ARTIFACT,
    CardType.PLANESWALKER, CardType.LAND,
}


class GenesisWave(Sorcery):
    """Genesis Wave — {X}{G}{G}{G} — Sorcery.

    Reveal the top X cards of your library. You may put any number of
    permanent cards with mana value X or less from among them onto the
    battlefield. Then put all cards revealed this way that weren't put
    onto the battlefield into your graveyard.

    FDN collector number 221.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Genesis Wave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}{G}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Reveal the top X cards of your library. You may put any number "
            "of permanent cards with mana value X or less from among them "
            "onto the battlefield. Then put all cards revealed this way that "
            "weren't put onto the battlefield into your graveyard.",
        )
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Reveal top X, put eligible permanents onto battlefield, rest to graveyard."""
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        x = self.x_value
        if x <= 0:
            return

        library = controller.zones[Zone.LIBRARY]
        lib_cards = list(library.get_all())

        # Top of library is end of list
        revealed = lib_cards[-x:] if len(lib_cards) >= x else list(lib_cards)

        # Determine eligible permanents (mana value <= X)
        eligible: list[Any] = []
        for card in revealed:
            card_types = getattr(card, "card_types", set())
            if card_types & _PERMANENT_TYPES:
                mc = getattr(card, "mana_cost", None)
                mv = mc.cmc if mc else 0
                if mv <= x:
                    eligible.append(card)

        # Oracle: "You may put any number of permanent cards...onto the
        # battlefield."  Ask the controller's agent to choose which
        # eligible permanents to keep; default to all if no agent.
        chosen = eligible
        if hasattr(controller, "choose_cards"):
            chosen = controller.choose_cards(
                eligible,
                min_count=0,
                max_count=len(eligible),
                prompt="Choose permanent cards to put onto the battlefield.",
            )

        # Put chosen onto battlefield
        put_onto_bf: set[int] = set()
        for card in chosen:
            card.controller = controller
            move_to_zone(game, card, Zone.LIBRARY, Zone.BATTLEFIELD)
            put_onto_bf.add(id(card))

        # Rest go to graveyard
        for card in revealed:
            if id(card) not in put_onto_bf:
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
