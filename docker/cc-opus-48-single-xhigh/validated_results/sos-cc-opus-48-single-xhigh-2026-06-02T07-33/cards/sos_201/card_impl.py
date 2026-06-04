"""Card implementation for Lorehold, the Historian (SOS 201)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.  (You may cast a
    card for its miracle cost when you draw it if it's the first card you drew
    this turn.)
    At the beginning of each opponent's upkeep, you may discard a card.  If you
    do, draw a card.

    SOS collector number 201.
    """

    #: The miracle cost Lorehold grants to instants/sorceries in its
    #: controller's hand.  "Miracle" is a printed keyword label, NOT an
    #: evergreen ``engine.types.Keyword`` enum member (that enum is frozen at
    #: 16 members), so it is recorded as a printed-keyword label below.
    MIRACLE_LABEL = "Miracle"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Dragon", "Elder"})
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
        # Explicit colour identity (R+W) so the colour is stable even when the
        # cost is unavailable (e.g. on copies); the cost pips already encode it.
        self.colors: list[Color] = [Color.RED, Color.WHITE]
        # Printed-keyword label surface — Miracle is a printed keyword, not an
        # evergreen ``Keyword`` enum member.
        self.printed_keywords: list[str] = [self.MIRACLE_LABEL]

    # ------------------------------------------------------------------
    # Miracle grant — queryable surface
    # ------------------------------------------------------------------

    def get_miracle_cost(self, game: "GameState", card: Any) -> ManaCost | None:
        """Return the miracle cost this card grants to *card*, or ``None``.

        Lorehold grants miracle {2} to every instant and sorcery card in *its
        controller's* hand.  This is the queryable grant surface the tests probe:
        it returns ``{2}`` only when

        * Lorehold is on the battlefield,
        * *card* is an instant or a sorcery, and
        * *card* is in Lorehold's controller's hand,

        and ``None`` otherwise (creatures, an opponent's hand card, etc.).
        """
        from engine.miracle import MIRACLE_TWO, is_instant_or_sorcery

        controller = self.controller
        if controller is None:
            return None
        if not _is_on_battlefield(game, self):
            return None
        if not is_instant_or_sorcery(card):
            return None
        if not game.get_hand(controller).contains(card):
            return None
        return MIRACLE_TWO

    # ------------------------------------------------------------------
    # Continuous grant + draw-time hook wiring
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the loot trigger, the miracle grant, and the draw hook."""
        self._register_upkeep_loot(game)
        self._apply_miracle_grant(game)
        self._register_miracle_draw_hook(game)

    def register_replacement_effects(self, game: "GameState") -> None:
        """Refresh the miracle grant whenever effects are recomputed."""
        self._apply_miracle_grant(game)

    def _apply_miracle_grant(self, game: "GameState") -> None:
        """Write miracle {2} onto every instant/sorcery in the controller's hand.

        Reuses the additive :func:`engine.miracle.grant_miracle_to_hand` so the
        grant is queryable both via :meth:`get_miracle_cost` (above) and via the
        ``miracle_cost`` attribute the framework writes onto each affected hand
        card.  No-ops while Lorehold is not on the battlefield.
        """
        from engine.miracle import MIRACLE_TWO, clear_miracle_grants, grant_miracle_to_hand

        controller = self.controller
        if controller is None:
            return
        if not _is_on_battlefield(game, self):
            clear_miracle_grants(game, self)
            return
        grant_miracle_to_hand(game, self, controller, MIRACLE_TWO)

    def _register_miracle_draw_hook(self, game: "GameState") -> None:
        """Wire the draw-time miracle cast hook (CR 702.94a)."""
        from engine.miracle import register_miracle_draw_hook

        controller = self.controller or game.active_player
        register_miracle_draw_hook(
            game, self, controller, cost_resolver=self.get_miracle_cost
        )

    # ------------------------------------------------------------------
    # Loot trigger — "at the beginning of each opponent's upkeep"
    # ------------------------------------------------------------------

    def _register_upkeep_loot(self, game: "GameState") -> None:
        """Register the each-opponent's-upkeep optional loot trigger."""
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Refresh the miracle grant on each upkeep so newly-drawn / -added
            # hand cards keep an up-to-date grant surface.
            source._apply_miracle_grant(g)
            # "each opponent's upkeep" — fire only when the active player is an
            # opponent (i.e. NOT the controller).
            return g.active_player is not ctrl

        def _effect(g: "GameState") -> None:
            source._resolve_loot(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _resolve_loot(self, game: "GameState") -> None:
        """Resolve the loot ability: may discard a card; if you do, draw one.

        Optional ("you may discard a card") and conditional ("If you do, draw a
        card").  Declining or having an empty hand discards nothing and draws
        nothing.
        """
        from engine.game import discard, draw_card

        controller = self.controller
        if controller is None:
            return

        hand = game.get_hand(controller)
        hand_cards = list(hand.get_all())
        if not hand_cards:
            # Empty hand — nothing to discard, so no draw.
            return

        chooser = getattr(controller, "choose_yes_no", None)
        if not callable(chooser):
            return
        try:
            wants = bool(chooser("Discard a card to draw a card?"))
        except Exception:
            return
        if not wants:
            # Declined — no discard, so (conditionally) no draw.
            return

        # Choose which card to discard.
        picker = getattr(controller, "choose_card", None)
        chosen = None
        if callable(picker):
            try:
                chosen = picker(hand_cards, "card to discard")
            except Exception:
                chosen = None
        if chosen is None or not hand.contains(chosen):
            # No valid discard selection — treat as no discard (no draw).
            return

        discard(game, controller, chosen)
        # "If you do, draw a card." — the draw is gated on the discard having
        # happened.
        draw_card(game, controller)
