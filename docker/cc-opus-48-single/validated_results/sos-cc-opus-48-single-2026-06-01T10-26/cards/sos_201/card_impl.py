"""Card implementation for Lorehold, the Historian (SOS 201)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


# Card types that gain miracle from Lorehold's static ability.
_INSTANT_OR_SORCERY = frozenset({CardType.INSTANT, CardType.SORCERY})

# The miracle cost Lorehold grants: {2}.
_MIRACLE_COST = ManaCost.parse("{2}")


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return ``True`` if *card* is an instant or sorcery card."""
    return bool(getattr(card, "card_types", set()) & _INSTANT_OR_SORCERY)


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may cast a
    card for its miracle cost when you draw it if it's the first card you drew
    this turn.)
    At the beginning of each opponent's upkeep, you may discard a card. If you
    do, draw a card.

    SOS collector number 201.
    """

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

    # ------------------------------------------------------------------
    # Miracle grant — "Each instant and sorcery card in your hand has
    # miracle {2}."
    # ------------------------------------------------------------------

    def miracle_cost(self, game: "GameState", card: Any) -> "ManaCost | None":
        """Return the miracle cost Lorehold grants to *card*, or ``None``.

        This doubles as Lorehold's *grant API*: the engine's draw-time miracle
        hook (``engine.miracle.derive_miracle_cost``) discovers each battlefield
        permanent that exposes a callable ``miracle_cost(game, card)`` and asks
        it for the cost of the just-drawn card.  Because the cost is derived
        dynamically every draw, the grant is NOT sticky — once Lorehold leaves
        play this method is no longer consulted, so a card stamped earlier stops
        offering miracle (the hook clears the stale stamp).

        The grant is scoped to instant/sorcery cards that are in *this card's
        controller's hand* while Lorehold is in play (a naturally-drawn card is
        already in hand when the hook runs, so it qualifies with no manual
        pre-stamping); everything else (other card types, cards in an opponent's
        hand) gets ``None``.

        As a convenience the engine-level ``miracle_cost`` attribute is also
        stamped onto qualifying cards via :func:`engine.miracle.set_miracle_cost`.
        """
        from engine.miracle import set_miracle_cost

        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if self._grants_miracle_to(game, card, controller):
            set_miracle_cost(card, _MIRACLE_COST)
            return _MIRACLE_COST
        return None

    def _grants_miracle_to(
        self, game: "GameState", card: Any, controller: Any
    ) -> bool:
        """Return ``True`` if Lorehold grants miracle to *card* right now."""
        if controller is None:
            return False
        if not _is_instant_or_sorcery(card):
            return False
        # "in your hand": the card must be in the controller's hand.
        hand = game.get_hand(controller)
        return hand.contains(card)

    def apply_miracle_grant(self, game: "GameState") -> None:
        """Stamp miracle {2} onto every qualifying card in the controller's hand.

        Convenience for callers (and the engine) that want to refresh the grant
        across the whole hand at once — e.g. after Lorehold enters or after the
        controller draws.  Idempotent.
        """
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return
        for card in game.get_hand(controller).get_all():
            self.miracle_cost(game, card)

    # ------------------------------------------------------------------
    # Opponent-upkeep loot trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the 'each opponent's upkeep' optional loot trigger.

        ``BeginningOfUpkeepTriggeredEvent`` carries no player field, so the
        condition reads ``game.active_player`` (the player whose upkeep it is)
        and fires only when that player is NOT the controller.
        """
        from engine.triggers import TriggerRegistration

        controller = getattr(self, "controller", None) or getattr(self, "owner", None)

        def _condition(g: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            # Fire only on an OPPONENT's upkeep (active player != controller).
            return g.active_player is not controller

        def _effect(g: "GameState") -> None:
            _loot(g, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _loot(game: "GameState", controller: Any) -> None:
    """Resolve "you may discard a card. If you do, draw a card."

    Contract for the deterministic test pipeline:

    * ``controller.choose_yes_no`` drives the optional "you may" clause —
      script ``True`` to loot, ``False`` to decline.
    * ``controller.choose_card`` selects the card to discard.
    * The draw happens only if a card was actually discarded ("If you do").
      With an empty hand there is nothing to discard, so the draw is skipped
      regardless of the yes/no answer.
    """
    from engine.game import discard, draw_card

    if controller is None:
        return

    hand = game.get_hand(controller)
    cards = hand.get_all()
    # "If you do" is conditional on actually discarding; with no card to
    # discard, nothing happens (and we don't prompt for a draw).
    if not cards:
        return

    if hasattr(controller, "choose_yes_no"):
        if not controller.choose_yes_no("Discard a card to draw a card?"):
            return

    chosen = controller.choose_card(cards, "card to discard")
    if chosen is None or not hand.contains(chosen):
        return

    discard(game, controller, chosen)
    # Discard succeeded — draw a card.
    draw_card(game, controller)
