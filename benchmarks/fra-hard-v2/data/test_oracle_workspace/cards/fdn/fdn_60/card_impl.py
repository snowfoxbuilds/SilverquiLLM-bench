"""Card implementation for Gutless Plunderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.card_queries import choose_object
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class GutlessPlundererAbility1:
    text = 'Deathtouch (Any amount of damage this deals to a creature is enough to destroy it.)'


class GutlessPlundererAbility2:
    text = 'Raid — When this creature enters, if you attacked this turn, look at the top three cards of your library. You may put one of those cards back on top of your library. Put the rest into your graveyard.'


# endregion Printed abilities


class GutlessPlunderer(Creature):
    """Gutless Plunderer — {2}{B} — 2/2 — Skeleton Pirate — Deathtouch.

    Raid — When this creature enters, if you attacked this turn, look at
    the top three cards of your library. You may put one of those cards
    back on top of your library. Put the rest into your graveyard.

    FDN collector number 60.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gutless Plunderer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Skeleton", "Pirate"})
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Deathtouch\nRaid — When this creature enters, if you attacked "
            "this turn, look at the top three cards of your library. You may "
            "put one of those cards back on top of your library. Put the rest "
            "into your graveyard.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        def _condition(game: Any, controller: Any) -> bool:
            return bool(getattr(controller, "attacked_this_turn", False))

        register_enters_trigger(game, self, GutlessPlundererAbility2, self._enters, condition=_condition)

    def _enters(self, game: "GameState", controller: Any) -> None:
        """ETB with Raid: look at top 3, keep one on top, rest to graveyard."""
        from engine.zones import move_to_zone

        if controller is None:
            return

        # Check raid condition
        # Raid: the engine records a declared attack on the attacking player.
        attacked = getattr(controller, "attacked_this_turn", False)
        if not attacked:
            return

        library = controller.zones[Zone.LIBRARY]
        cards = library.get_all()
        top_three = cards[-3:] if len(cards) >= 3 else cards[:]

        if not top_three:
            return

        # Choose one to keep on top (optional)
        chosen = choose_object(game, controller, top_three, "card to keep on top of library", source_card=self, optional=True)
        # Move the rest to graveyard
        for card in top_three:
            if card is chosen:
                continue
            move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
