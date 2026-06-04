"""Card implementation for Lorehold, the Historian (SOS 201).

Lorehold, the Historian is a ``{3}{R}{W}`` Legendary Creature — Elder Dragon,
5/5, with flying and haste. It grants miracle ``{2}`` to instant and sorcery
cards in its controller's hand, and at the beginning of each opponent's upkeep
its controller may rummage (discard a card; if they do, draw a card).

Miracle (CR 702.94) has no native engine pipeline. The granting is exposed
through two surfaces:

* ``MIRACLE_COST`` / ``grant_miracle`` — the observable static-ability portion:
  stamp ``miracle_cost`` onto eligible hand cards (used by the existing tests).
* ``grants_miracle_to`` — the capability the additive draw-time miracle pipeline
  in :mod:`engine.game` / :mod:`engine.casting` queries when a card is drawn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If you
    do, draw a card.

    SOS collector number 201.
    """

    # The granted alternative (miracle) cost is {2} generic. Exposed as a
    # class constant so the static-ability contract and the draw-time pipeline
    # share a single source of truth.
    MIRACLE_COST: ManaCost = ManaCost.parse("{2}")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Explicit color identity (KEY_DECISIONS sos_13 convention).
        self.colors: list[str] = ["R", "W"]

    # ------------------------------------------------------------------
    # Miracle granting
    # ------------------------------------------------------------------

    def grants_miracle_to(self, card: Any) -> ManaCost | None:
        """Return the miracle cost this permanent grants *card*, else ``None``.

        Lorehold grants miracle ``{2}`` to every instant and sorcery card; any
        other card type (creature, land, etc.) gets nothing. This is the
        capability the additive draw-time miracle pipeline queries on permanents
        the drawing player controls.
        """
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return self.MIRACLE_COST
        return None

    def grant_miracle(self, game: "GameState") -> None:
        """Stamp ``miracle_cost`` onto eligible cards in the controller's hand.

        "Each instant and sorcery card in *your* hand has miracle {2}." Marks
        every instant/sorcery card in this card's controller's hand with the
        granted alternative cost; non-cast types and other players' hands are
        left untouched.
        """
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        hand = game.get_hand(controller)
        for card in hand.get_all():
            cost = self.grants_miracle_to(card)
            if cost is not None:
                card.miracle_cost = cost  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Opponent's-upkeep rummage trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the beginning-of-each-opponent's-upkeep rummage trigger."""
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: Any) -> bool:
            # "each opponent's upkeep" — fire only when the active player (whose
            # upkeep is beginning) is NOT this card's controller. The event
            # carries no player, so read the game's active player.
            return game.active_player is not source.controller

        def _effect(game: "GameState") -> None:
            from engine.game import draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # "you may discard a card."
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return

            hand = game.get_hand(ctrl)
            hand_cards = hand.get_all()
            if not hand_cards:
                # Nothing to discard — "if you do" fails, so no draw. Safe no-op.
                return

            chosen = ctrl.choose_card(hand_cards, "Choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return

            # Discard the chosen card to the graveyard.
            from engine.types import Zone
            from engine.zones import move_to_zone

            move_to_zone(game, chosen, Zone.HAND, Zone.GRAVEYARD)

            # "If you do, draw a card."
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
