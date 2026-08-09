"""Card implementation for Vivien Reid."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.card_queries import choose_object
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


class VivienReid(Planeswalker):
    """Vivien Reid — {3}{G}{G} — 5 loyalty.

    +1: Look at the top four cards. May reveal a creature or land and put
        it into your hand. Rest on bottom in random order.
    −3: Destroy target artifact, enchantment, or creature with flying.
    −8: Emblem — creatures you control get +2/+2 and have vigilance,
        trample, and indestructible.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vivien Reid")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("starting_loyalty", 5)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vivien"}
        kwargs.setdefault(
            "rules_text",
            "+1: Look at the top four cards of your library. You may reveal a "
            "creature or land card from among them and put it into your hand. "
            "Put the rest on the bottom of your library in a random order.\n"
            "−3: Destroy target artifact, enchantment, or creature with flying.\n"
            "−8: You get an emblem with \"Creatures you control get +2/+2 and have "
            "vigilance, trample, and indestructible.\"",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Look at top 4 cards, may reveal a creature or land to hand."""
            import random

            controller = pw.controller
            if controller is None:
                return

            library = controller.zones[Zone.LIBRARY]
            hand = controller.zones[Zone.HAND]
            if len(library) == 0:
                return

            # Get top 4 cards (top = end of list)
            all_cards = library.get_all()
            count = min(4, len(all_cards))
            top_cards = all_cards[-count:]

            # Find creature or land cards among the top cards
            eligible = [
                card for card in top_cards
                if CardType.CREATURE in getattr(card, "card_types", set())
                or CardType.LAND in getattr(card, "card_types", set())
            ]

            # Let the controller choose one (optional — "you may")
            found = None
            if eligible:
                chosen = choose_object(
                    game, controller, eligible, "You may reveal a creature or land card", source_card=pw, optional=True
                )
                # Controller may decline (None means no choice)
                if chosen is not None and chosen in eligible:
                    found = chosen

            # Put the chosen card into hand
            if found is not None:
                library.remove(found)
                hand.add(found)
                top_cards = [c for c in top_cards if c is not found]

            # Put the rest on the bottom in random order
            remaining = [c for c in top_cards if library.contains(c)]
            for c in remaining:
                library.remove(c)
            random.shuffle(remaining)
            for c in remaining:
                library.add(c, position="bottom")

        def _is_minus3_legal(obj: Any) -> bool:
            """Artifact, enchantment, or creature with flying."""
            card_types = getattr(obj, "card_types", set())
            keywords = getattr(obj, "keywords", Keyword(0))
            return (
                CardType.ARTIFACT in card_types
                or CardType.ENCHANTMENT in card_types
                or (CardType.CREATURE in card_types and Keyword.FLYING in keywords)
            )

        def _minus3_targeting(
            game: Any, source: Any, controller: Any
        ) -> list[Any] | None:
            """Required target — no legal permanent ⇒ cannot be activated."""
            candidates = [
                obj
                for player in game.players
                for obj in game.get_battlefield(player).get_all()
                if _is_minus3_legal(obj)
            ]
            if not candidates:
                return None
            chosen = choose_object(
                game,
                controller,
                candidates,
                "Destroy target artifact, enchantment, or creature with flying",
                source_card=source,
            )
            if chosen is None:
                return None
            return [chosen]

        def _minus3(game: Any, targets: list[Any], context: Any = None) -> None:
            """Destroy the chosen target — revalidated at resolution."""
            from engine.game import destroy

            target = targets[0] if targets else None
            if target is None:
                return
            if not any(
                game.get_battlefield(p).contains(target) for p in game.players
            ):
                return
            # Revalidate the target's characteristics at resolution.
            if _is_minus3_legal(target):
                destroy(game, target)

        def _minus8(game: Any) -> None:
            """Emblem — creatures you control get +2/+2, vigilance, trample, indestructible."""
            from engine.continuous_effects import (
                ContinuousEffect,
                DURATION_PERMANENT,
                Layer,
                SubLayer,
            )

            controller = pw.controller
            if controller is None:
                return

            # Create a sentinel emblem source that won't be removed
            emblem = type("Emblem", (), {"name": "Vivien Reid Emblem"})()

            # Register continuous effect for P/T boost (Layer 7c)
            def _apply_pt(game: Any) -> None:
                """Give creatures controlled by emblem owner +2/+2."""
                bf = game.get_battlefield(controller)
                for obj in bf.get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        obj.modified_power += 2
                        obj.modified_toughness += 2

            game.effect_manager.add(ContinuousEffect(
                source=emblem,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_pt,
                duration=DURATION_PERMANENT,
            ))

            # Register continuous effect for keywords (Layer 6)
            def _apply_keywords(game: Any) -> None:
                """Give creatures controlled by emblem owner vigilance, trample, indestructible."""
                bf = game.get_battlefield(controller)
                for obj in bf.get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        obj.keywords = (
                            getattr(obj, "keywords", Keyword(0))
                            | Keyword.VIGILANCE
                            | Keyword.TRAMPLE
                            | Keyword.INDESTRUCTIBLE
                        )

            game.effect_manager.add(ContinuousEffect(
                source=emblem,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_keywords,
                duration=DURATION_PERMANENT,
            ))

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Look at top 4, may reveal creature or land to hand.",
            ),
            LoyaltyAbility(
                loyalty_cost=-3,
                effect=_minus3,
                targeting=_minus3_targeting,
                description="−3: Destroy target artifact, enchantment, or creature with flying.",
            ),
            LoyaltyAbility(
                loyalty_cost=-8,
                effect=_minus8,
                description="−8: Emblem — creatures get +2/+2, vigilance, trample, indestructible.",
            ),
        ]
