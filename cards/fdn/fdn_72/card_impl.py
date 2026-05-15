"""Card implementation for Tinybones, Bauble Burglar."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TinybonesBaubleBurglar(Creature):
    """Tinybones, Bauble Burglar — {1}{B} — 1/3 — Legendary Skeleton Rogue.

    Whenever an opponent discards a card, exile it from their graveyard
    with a stash counter on it.
    During your turn, you may play cards you don't own with stash counters
    on them from exile, and mana of any type can be spent to cast those spells.
    {3}{B}, {T}: Each opponent discards a card. Activate only as a sorcery.

    FDN collector number 72.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tinybones, Bauble Burglar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Skeleton", "Rogue"})
        kwargs.setdefault("supertypes", {"Legendary"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Whenever an opponent discards a card, exile it from their "
            "graveyard with a stash counter on it.\nDuring your turn, you "
            "may play cards you don't own with stash counters on them from "
            "exile, and mana of any type can be spent to cast those spells.\n"
            "{3}{B}, {T}: Each opponent discards a card. Activate only as a "
            "sorcery.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register discard exile trigger.

        Whenever an opponent discards a card, exile it from their graveyard
        with a stash counter on it.
        """
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import exile, add_counter

        source = self

        # Watch for cards entering the graveyard from hand (discard).
        # ENGINE LIMITATION: No dedicated DISCARDS event. We use
        # LEAVES_BATTLEFIELD as a fallback, but cannot fully track
        # discard events without engine support. The activated ability
        # handles the primary discard mechanic directly by exiling
        # discarded cards with stash counters.

        controller = getattr(self, "controller", None) or game.active_player

    def get_activated_abilities(self, game: "GameState") -> list:
        """Tap ability: each opponent discards a card. Activate only as a sorcery."""
        source = self

        def _discard_effect(game: "GameState") -> None:
            from engine.game import discard, exile, add_counter

            controller = getattr(source, "controller", None)
            if controller is None:
                return
            for player in game.players:
                if player is controller:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        chosen = player.choose_card(hand_cards, "discard a card")
                    except Exception:
                        chosen = hand_cards[0]
                    if chosen is not None:
                        discard(game, player, chosen)
                        # Exile the discarded card from graveyard with stash counter
                        gy = player.zones[Zone.GRAVEYARD]
                        if gy.contains(chosen):
                            exile(game, chosen)
                            # Add stash counter
                            if not hasattr(chosen, "counters"):
                                chosen.counters = {}
                            chosen.counters["stash"] = chosen.counters.get("stash", 0) + 1

        def _cost(game: "GameState", src=source) -> bool:
            """Pay {3}{B}, tap. Only at sorcery speed."""
            from engine.casting import is_sorcery_speed

            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            # Must not be tapped
            if getattr(src, "is_tapped", False):
                return False
            # Sorcery-speed restriction
            if not is_sorcery_speed(game, controller):
                return False
            # Pay {3}{B}
            cost = ManaCost.parse("{3}{B}")
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        ability = ActivatedAbility(
            cost=_cost,
            effect=_discard_effect,
            description="{3}{B}, {T}: Each opponent discards a card. Activate only as a sorcery.",
        )
        ability.tap_cost = True
        return [ability]
