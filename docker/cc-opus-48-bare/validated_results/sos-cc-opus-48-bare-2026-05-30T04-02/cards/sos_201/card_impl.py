"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# The miracle cost Lorehold grants to your instant/sorcery cards.
_MIRACLE_COST: ManaCost = ManaCost(generic=2)


def _on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if player.zones[Zone.BATTLEFIELD].contains(obj):
            return True
    return False


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If
    you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        self.colors: list[str] = ["R", "W"]

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player
        self._register_miracle(game, source, controller)
        self._register_loot(game, source, controller)

    # ------------------------------------------------------------------
    # Miracle {2} for your instant/sorcery cards
    # ------------------------------------------------------------------

    def _register_miracle(self, game: GameState, source: Any, controller: Any) -> None:
        drawn = [None]  # mutable cell carrying the event's card to the effect

        def _condition(game: GameState, event: DrawsCardTriggeredEvent) -> bool:
            if not _on_battlefield(game, source):
                return False
            owner = source.controller
            if owner is None or getattr(event, "player", None) is not owner:
                return False
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            # Miracle only applies to the first card you draw in a turn.
            if getattr(owner, "cards_drawn_this_turn", 0) != 1:
                return False
            drawn[0] = card
            return True

        def _effect(game: GameState) -> None:
            owner = source.controller
            card = drawn[0]
            if owner is None or card is None:
                return
            hand = owner.zones[Zone.HAND]
            if not hand.contains(card):
                return
            if not owner.mana_pool.can_pay(_MIRACLE_COST):
                return
            if not owner.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            from engine.casting import cast_spell_free

            owner.mana_pool.pay(_MIRACLE_COST)
            cast_spell_free(game, owner, card, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Loot on each opponent's upkeep
    # ------------------------------------------------------------------

    def _register_loot(self, game: GameState, source: Any, controller: Any) -> None:
        def _condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            if not _on_battlefield(game, source):
                return False
            owner = source.controller
            if owner is None:
                return False
            upkeep_player = getattr(event, "player", None)
            return upkeep_player is not None and upkeep_player is not owner

        def _effect(game: GameState) -> None:
            from engine.game import discard, draw_card

            owner = source.controller
            if owner is None:
                return
            hand = owner.zones[Zone.HAND]
            if len(hand) == 0:
                return
            if not owner.choose_yes_no("Discard a card to draw a card?"):
                return
            card = owner.choose_card(hand.get_all(), "Choose a card to discard")
            if card is None or not hand.contains(card):
                return
            discard(game, owner, card)
            draw_card(game, owner)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
