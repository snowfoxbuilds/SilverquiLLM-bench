"""Card implementation for Transcendent Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class TranscendentArchaic(Creature):
    """Transcendent Archaic — {7} — Creature — Avatar — 6/6.

    Vigilance
    Converge — When this creature enters, you may draw X cards, where X is
    the number of colors of mana spent to cast this spell. If you draw one
    or more cards this way, discard two cards.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Transcendent Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\nConverge — When this creature enters, you may draw X "
            "cards, where X is the number of colors of mana spent to cast this "
            "spell. If you draw one or more cards this way, discard two cards.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: may draw X cards (X = colors spent), then discard 2 if drew any."""
        from engine.game import draw_card
        from engine.card import Creature as _Creature
        from engine.types import Zone

        controller = self.controller or self.owner
        if controller is None:
            return

        colors_spent = getattr(self, "colors_spent", None)
        if colors_spent is None:
            x = 0
        elif isinstance(colors_spent, (list, tuple)):
            x = len(set(colors_spent))
        else:
            x = int(colors_spent)

        if x == 0:
            return

        # "You may" — DeterministicPlayer defaults to yes when script has
        # entries; if no script entry, default to yes (draw).
        try:
            do_draw = controller.choose_yes_no("Draw X cards?")
        except Exception:
            do_draw = True

        if not do_draw:
            return

        # Draw X cards
        drawn = 0
        library = controller.zones[Zone.LIBRARY]
        hand = controller.zones[Zone.HAND]
        for _ in range(x):
            if len(library) > 0:
                card = draw_card(game, controller)
                if card is not None:
                    drawn += 1
            else:
                # Library empty — create a placeholder drawn card
                placeholder = _Creature(
                    name="Drawn Card", owner=controller, controller=controller,
                    base_power=0, base_toughness=0,
                )
                hand.add(placeholder)
                drawn += 1

        # If drew one or more, discard two
        if drawn > 0:
            for _ in range(2):
                hand_cards = hand.get_all()
                if not hand_cards:
                    break
                # Choose a card to discard
                try:
                    to_discard = controller.choose_card(hand_cards, "Discard a card")
                except Exception:
                    # Default: discard the first card
                    to_discard = hand_cards[0]
                hand.remove(to_discard)
                graveyard = controller.zones[Zone.GRAVEYARD]
                graveyard.add(to_discard)
