"""Card implementation for Lorehold, the Historian (SOS 201)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


# The granted miracle cost — "miracle {2}".
_MIRACLE_COST_STR = "{2}"


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return ``True`` if *card* is an instant or sorcery card."""
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 Legendary Creature — Elder Dragon.

    - Flying, haste.
    - Each instant and sorcery card in your hand has miracle {2}.
      (You may cast a card for its miracle cost when you draw it if it's the
      first card you drew this turn.)
    - At the beginning of each opponent's upkeep, you may discard a card. If
      you do, draw a card.

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
            "(You may cast a card for its miracle cost when you draw it if it's "
            "the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Miracle granting (static half)
    # ------------------------------------------------------------------

    def _controller(self) -> Any:
        return getattr(self, "controller", None) or getattr(self, "owner", None)

    def get_miracle_cost(self, game: "GameState", card: Any) -> ManaCost | None:
        """Return the granted miracle cost for *card*, or ``None``.

        "Each instant and sorcery card in your hand has miracle {2}." The grant
        is restricted to instants/sorceries that are in *Lorehold's controller's*
        hand. Anything else (wrong type, wrong zone, wrong controller) gets no
        miracle and returns ``None``.
        """
        controller = self._controller()
        if controller is None:
            return None
        if not _is_instant_or_sorcery(card):
            return None
        hand = game.get_hand(controller)
        if not hand.contains(card):
            return None
        return ManaCost.parse(_MIRACLE_COST_STR)

    # ------------------------------------------------------------------
    # Dynamic miracle window — "cast it when you draw it, first card this turn"
    # ------------------------------------------------------------------

    def register_miracle_window(self, game: "GameState") -> None:
        """Register Lorehold's miracle grant with the engine draw-window hook.

        While Lorehold is on the battlefield, the first instant/sorcery its
        controller draws each turn may be cast for the granted miracle cost
        ({2}). This routes through the additive
        ``engine.casting.cast_spell_alternative`` entry point and the
        ``engine.game`` miracle draw-window registry, both of which are no-ops
        when no grant is registered.
        """
        register = getattr(game, "register_miracle_grant", None)
        if register is None:
            return

        source = self
        controller = self._controller()

        def _grant(g: "GameState", drawing_player: Any, drawn_card: Any) -> Any:
            # Only the controller's own first draw, only instants/sorceries,
            # and only while Lorehold is on the battlefield.
            if controller is None or drawing_player is not controller:
                return None
            battlefield = g.get_battlefield(controller)
            if not battlefield.contains(source):
                return None
            if not _is_instant_or_sorcery(drawn_card):
                return None
            return ManaCost.parse(_MIRACLE_COST_STR)

        register(_grant, source=source, controller=controller)

    # ------------------------------------------------------------------
    # Opponent-upkeep loot trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the opponent-upkeep loot trigger.

        "At the beginning of each opponent's upkeep, you may discard a card. If
        you do, draw a card." The engine's ``BeginningOfUpkeepTriggeredEvent``
        carries no player field and fires for the active player's upkeep, so the
        opponent-vs-self distinction lives in the trigger's ``condition`` and is
        keyed off ``game.active_player`` (the controller's own upkeep does not
        fire this).
        """
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self._controller() or game.active_player

        # Also wire up the dynamic miracle window when triggers register
        # (typically as the permanent enters the battlefield).
        self.register_miracle_window(game)

        def _condition(g: Any, event: Any) -> bool:
            # Fires only on an opponent's upkeep — i.e. when the active player
            # is someone other than Lorehold's controller.
            return getattr(g, "active_player", None) is not controller

        def _effect(g: "GameState") -> None:
            source._loot(g, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _loot(self, game: "GameState", controller: Any) -> None:
        """"you may discard a card; if you do, draw a card." """
        from engine.game import discard, draw_card

        if controller is None:
            return

        hand = game.get_hand(controller)
        hand_cards = list(hand.get_all())

        # "you may discard" — ask the controller. Even with an empty hand we
        # still consult so a declining script answer is consumed cleanly; but
        # an empty hand simply can't discard, so it's a no-op.
        choose_yes_no = getattr(controller, "choose_yes_no", None)
        wants = False
        if choose_yes_no is not None:
            try:
                wants = bool(choose_yes_no("Discard a card to draw a card?"))
            except Exception:
                wants = False

        if not wants or not hand_cards:
            return

        # Choose which card to discard.
        choose_card = getattr(controller, "choose_card", None)
        pitch = None
        if choose_card is not None:
            try:
                pitch = choose_card(hand_cards, "Choose a card to discard")
            except Exception:
                pitch = None
        if pitch is None or not hand.contains(pitch):
            return

        discard(game, controller, pitch)
        draw_card(game, controller)
