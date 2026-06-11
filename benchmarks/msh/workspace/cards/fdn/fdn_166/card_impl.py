"""Card implementation for Time Stop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.card_queries import choose_object
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TimeStop(Instant):
    """Time Stop — {4}{U}{U} — Instant.

    End the turn. (Exile all spells and abilities on the stack, including
    this card. The player whose turn it is discards down to their maximum
    hand size. Damage heals and "this turn" and "until end of turn" effects
    end.)

    FDN collector number 166.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Time Stop")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "End the turn.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """End the turn — exile everything on the stack, clean up."""
        # Exile all spells and abilities on the stack
        stack_items = list(game.stack._items)  # noqa: SLF001
        game.stack._items.clear()  # noqa: SLF001

        for stack_obj in stack_items:
            card = getattr(stack_obj, "source", None)
            if card is None:
                continue
            controller = getattr(stack_obj, "controller", None)
            owner = getattr(card, "owner", controller)
            # Check if this is a spell (card is in the stack zone) vs an ability
            # For spells, exile the card. For abilities, just remove from stack.
            is_spell_on_stack = False
            if controller is not None:
                stack_zone = controller.zones[Zone.STACK]
                if stack_zone.contains(card):
                    stack_zone.remove(card)
                    is_spell_on_stack = True
            # Only exile cards that were spells on the stack
            if is_spell_on_stack and owner is not None:
                exile = owner.zones[Zone.EXILE]
                exile.add(card)

        # Discard down to max hand size for active player
        active = game.active_player
        if active is not None:
            max_hand = getattr(active, "max_hand_size", 7)
            hand = active.zones[Zone.HAND]
            hand_cards = list(hand.get_all())
            while len(hand_cards) > max_hand:
                from engine.game import discard
                try:
                    chosen = choose_object(
                        game, active, hand_cards, "Discard down to hand size", source_card=self
                    )
                except Exception:
                    chosen = hand_cards[-1]
                if chosen is not None:
                    discard(game, active, chosen)
                    hand_cards.remove(chosen)
                else:
                    break

        # ENGINE LIMITATION: Full "end the turn" implementation would need
        # to clear damage, remove until-end-of-turn effects, skip remaining
        # phases, and go directly to cleanup. The engine doesn't have a
        # phase-skipping mechanism.
        game._turn_ended = True  # noqa: SLF001
