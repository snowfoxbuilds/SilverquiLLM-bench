"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
    """

    def __init__(self, owner: Any = None, controller: Any = None, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "supertypes",
            {Supertype.LEGENDARY},
        )
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault(
            "keywords",
            Keyword.FLYING | Keyword.HASTE,
        )
        kwargs.setdefault(
            "rules_text",
            (
                "Flying, haste. "
                "Each instant and sorcery card in your hand has miracle {2}. "
                "At the beginning of each opponent's upkeep, you may discard a card. "
                "If you do, draw a card."
            ),
        )
        super().__init__(owner=owner, controller=controller, **kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register upkeep (discard/draw) and DrawsCard (miracle) triggers."""
        from engine.triggers import TriggerRegistration
        from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
        from engine.types import CardType, Zone

        source = self
        controller = self.controller

        # ------------------------------------------------------------------
        # 1. Opponent-upkeep trigger: may discard a card; if so, draw a card
        # ------------------------------------------------------------------

        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            # Fires only during an opponent's upkeep
            return game.active_player is not ctrl

        def _upkeep_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Ask controller if they want to discard
            wants_to_discard = ctrl.choose_yes_no(
                "At the beginning of an opponent's upkeep, you may discard a card."
                " If you do, draw a card."
            )
            if not wants_to_discard:
                return

            # Choose a card to discard
            hand = ctrl.zones[Zone.HAND].get_all()
            if not hand:
                return

            to_discard = ctrl.choose_card(list(hand), "Choose a card to discard")
            if to_discard is None:
                return

            discard(game, ctrl, to_discard)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )

        # ------------------------------------------------------------------
        # 2. DrawsCard trigger: miracle {2} for instants/sorceries on first draw
        # ------------------------------------------------------------------

        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Only fires for Lorehold's controller
            if event.player is not ctrl:
                return False
            # Only fires for the first card drawn this turn
            drawn = getattr(event.player, "cards_drawn_this_turn", 0)
            if drawn != 1:
                return False
            # Only fires for instants and sorceries
            card = event.card
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        # Use a mutable container so on_announce can pass the drawn card
        # to _miracle_effect when the trigger resolves.
        _miracle_card_ref: list[Any] = [None]

        def _miracle_on_announce(game: Any, event: Any) -> None:
            """Capture the drawn card at announcement time."""
            _miracle_card_ref[0] = getattr(event, "card", None)

        def _miracle_effect(game: "GameState") -> None:
            """Offer the controller the option to cast the drawn instant/sorcery for {2}."""
            from engine.casting import cast_spell_free, CastingError

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            card = _miracle_card_ref[0]
            if card is None:
                return

            # Only offer if the card is still in hand (player may have already cast it)
            hand = ctrl.zones[Zone.HAND]
            if not hand.contains(card):
                return

            # Ask the controller if they want to cast it for the miracle cost {2}
            wants_to_cast = ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            )
            if not wants_to_cast:
                return

            # Cast the spell for free (miracle cost {2} replaces the normal mana cost)
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except (CastingError, Exception):
                # If casting fails for any reason, silently decline
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
                on_announce=_miracle_on_announce,
            )
        )
