"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — Legendary Creature — Elder Dragon (5/5).

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
      If you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", {Keyword.FLYING, Keyword.HASTE})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.card import Instant, Sorcery
        from engine.casting import cast_spell_free
        from engine.events import DrawsCardTriggeredEvent, BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.types import ManaCost as MC

        source = self

        # ── Miracle trigger ─────────────────────────────────────────────────
        drawn_card: list[Any] = [None]

        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            card = event.card
            if not isinstance(card, (Instant, Sorcery)):
                return False
            drawn_count = getattr(event.player, "cards_drawn_this_turn", 0)
            if drawn_count != 1:
                return False
            drawn_card[0] = card
            return True

        def _miracle_effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            card = drawn_card[0]
            if card is None or ctrl is None:
                return
            # Ask if player wants to miracle cast
            try:
                want_miracle = ctrl._script.popleft()
            except Exception:
                want_miracle = False
            if not want_miracle:
                return
            # Card must be in hand to miracle cast
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            # Pay {2} miracle cost
            miracle_cost = MC.parse("{2}")
            if ctrl.mana_pool.can_pay(miracle_cost):
                ctrl.mana_pool.pay(miracle_cost)
            cast_spell_free(game, ctrl, card, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=source,
                controller=getattr(self, "controller", None),
            )
        )

        # ── Opponent upkeep: may discard → draw ────────────────────────────
        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return game.active_player is not ctrl

        def _upkeep_effect(game: Any) -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            try:
                want_discard = ctrl._script.popleft()
            except Exception:
                want_discard = False
            if not want_discard:
                return
            # Choose a card to discard
            hand = list(ctrl.zones[Zone.HAND].get_all())
            if not hand:
                return
            try:
                chosen = ctrl._script.popleft()
            except Exception:
                chosen = hand[0]
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=source,
                controller=getattr(self, "controller", None),
            )
        )

        from engine.card import Instant, Sorcery
        from engine.casting import cast_spell_free
        from engine.events import DrawsCardTriggeredEvent, BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.types import ManaCost as MC

        source = self

        # ── Miracle trigger ─────────────────────────────────────────────────
        drawn_card: list[Any] = [None]

        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            card = event.card
            if not isinstance(card, (Instant, Sorcery)):
                return False
            drawn_count = getattr(event.player, "cards_drawn_this_turn", 0)
            if drawn_count != 1:
                return False
            drawn_card[0] = card
            return True

        def _miracle_effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            card = drawn_card[0]
            if card is None or ctrl is None:
                return
            # Ask if player wants to miracle cast
            try:
                want_miracle = ctrl._script.popleft()
            except Exception:
                want_miracle = False
            if not want_miracle:
                return
            # Card must be in hand to miracle cast
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            # Pay {2} miracle cost
            miracle_cost = MC.parse("{2}")
            if ctrl.mana_pool.can_pay(miracle_cost):
                ctrl.mana_pool.pay(miracle_cost)
            cast_spell_free(game, ctrl, card, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=source,
                controller=getattr(self, "controller", None),
            )
        )

        # ── Opponent upkeep: may discard → draw ────────────────────────────
        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return game.active_player is not ctrl

        def _upkeep_effect(game: Any) -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            try:
                want_discard = ctrl._script.popleft()
            except Exception:
                want_discard = False
            if not want_discard:
                return
            # Choose a card to discard
            hand = list(ctrl.zones[Zone.HAND].get_all())
            if not hand:
                return
            try:
                chosen = ctrl._script.popleft()
            except Exception:
                chosen = hand[0]
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=source,
                controller=getattr(self, "controller", None),
            )
        )
