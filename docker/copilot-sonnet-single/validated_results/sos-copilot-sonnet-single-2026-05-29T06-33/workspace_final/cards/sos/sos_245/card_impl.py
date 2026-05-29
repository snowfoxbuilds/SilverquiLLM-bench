"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_creatures(game: "GameState", controller: Any) -> int:
    """Return the number of creature permanents the controller controls."""
    bf = game.get_battlefield(controller)
    return sum(
        1
        for card in bf.get_all()
        if CardType.CREATURE in getattr(card, "card_types", set())
    )


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Return 1 less for each creature the controller controls (affinity for creatures)."""
        controller = self.controller
        if controller is None:
            return 0
        return _count_creatures(game, controller)

    def register_triggers(self, game: "GameState") -> None:
        """Register the continuous effect granting affinity for creatures to instants/sorceries."""
        source = self

        def _apply_affinity_grant(g: "GameState") -> None:
            """Grant affinity_for_creatures to each instant/sorcery in controller's hand."""
            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            # Clear affinity_for_creatures from all hand instants/sorceries first,
            # so that when Witherbloom leaves the battlefield the grant is removed.
            for card in hand.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    if hasattr(card, "affinity_for_creatures"):
                        del card.affinity_for_creatures
                    # Also restore original cost_reduction if we monkey-patched it
                    if hasattr(card, "_affinity_cost_reduction_patched"):
                        # Remove the instance-level cost_reduction override
                        if "cost_reduction" in card.__dict__:
                            del card.__dict__["cost_reduction"]
                        del card._affinity_cost_reduction_patched

            # Check that Witherbloom is actually on the battlefield before re-granting
            bf = g.get_battlefield(ctrl)
            if not bf.contains(source):
                return

            for card in hand.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    card.affinity_for_creatures = True
                    # Patch cost_reduction on the instance to count creatures
                    def _make_cost_reduction(captured_ctrl):
                        def cost_reduction_fn(self_or_game, game_or_none=None):
                            # Handle both calling conventions:
                            # - card.cost_reduction(game) where self_or_game is `game`
                            #   if accessed as unbound (but we use types.MethodType so self is card)
                            if game_or_none is not None:
                                actual_game = game_or_none
                            else:
                                actual_game = self_or_game
                            return _count_creatures(actual_game, captured_ctrl)
                        return cost_reduction_fn

                    fn = _make_cost_reduction(ctrl)
                    card.cost_reduction = types.MethodType(fn, card)
                    card._affinity_cost_reduction_patched = True

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_affinity_grant,
            duration=DURATION_PERMANENT,
        ))
