"""Planeswalker card implementations (batch 2) from Foundations (FDN).

Implements the 3 remaining FDN planeswalkers not covered by ``planeswalkers.py``:

- **Kaito, Cunning Infiltrator** — {1}{U}{U}, 3 loyalty.
- **Chandra, Flameshaper** — {5}{R}{R}, 6 loyalty.
- **Vivien Reid** — {3}{G}{G}, 5 loyalty.

Each planeswalker subclasses :class:`~engine.card.Planeswalker` and
overrides :meth:`get_loyalty_abilities` to return fully implemented
loyalty abilities.

Use :func:`register_planeswalkers_batch2` to register these planeswalkers
with a :class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Kaito, Cunning Infiltrator
# ---------------------------------------------------------------------------

class KaitoCunningInfiltrator(Planeswalker):
    """Kaito, Cunning Infiltrator — {1}{U}{U} — 3 loyalty.

    Whenever a creature you control deals combat damage to a player, put a
    loyalty counter on Kaito.
    +1: Up to one target creature you control can't be blocked this turn.
        Draw a card, then discard a card.
    −2: Create a 2/1 blue Ninja creature token.
    −9: You get an emblem with "Whenever a player casts a spell, you create
        a 2/1 blue Ninja creature token."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kaito, Cunning Infiltrator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Kaito"}
        kwargs.setdefault(
            "rules_text",
            "Whenever a creature you control deals combat damage to a player, "
            "put a loyalty counter on Kaito.\n"
            "+1: Up to one target creature you control can't be blocked this turn. "
            "Draw a card, then discard a card.\n"
            "−2: Create a 2/1 blue Ninja creature token.\n"
            "−9: You get an emblem with \"Whenever a player casts a spell, you "
            "create a 2/1 blue Ninja creature token.\"",
        )
        super().__init__(**kwargs)

    # ENGINE LIMITATION: combat damage trigger for loyalty counters not implemented — requires combat damage events

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Up to one target creature can't be blocked. Draw then discard."""
            from engine.game import draw_card
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                target._cant_be_blocked = True  # type: ignore[attr-defined]
            controller = pw.controller
            if controller is not None:
                draw_card(game, controller)
                # Discard: remove last card from hand if any
                from engine.types import Zone
                hand = controller.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if cards_in_hand:
                    card_to_discard = cards_in_hand[-1]
                    hand.remove(card_to_discard)
                    gy = controller.zones[Zone.GRAVEYARD]
                    gy.add(card_to_discard)

        def _minus2(game: Any) -> None:
            """Create a 2/1 blue Ninja creature token."""
            from engine.game import create_token
            controller = pw.controller
            if controller is not None:
                token = Creature(
                    name="Ninja",
                    base_power=2,
                    base_toughness=1,
                    subtypes={"Ninja"},
                )
                create_token(game, controller, token)

        def _minus9(game: Any) -> None:
            """Emblem — whenever a player casts a spell, create a 2/1 Ninja token."""
            # ENGINE LIMITATION: emblem system not implemented — creates a single Ninja token as approximation
            from engine.game import create_token
            controller = pw.controller
            if controller is not None:
                token = Creature(
                    name="Ninja",
                    base_power=2,
                    base_toughness=1,
                    subtypes={"Ninja"},
                )
                create_token(game, controller, token)

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Target creature can't be blocked. Draw, then discard.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Create a 2/1 blue Ninja creature token.",
            ),
            LoyaltyAbility(
                loyalty_cost=-9,
                effect=_minus9,
                description="−9: Emblem — spell cast → create 2/1 Ninja token.",
            ),
        ]


# ---------------------------------------------------------------------------
# Chandra, Flameshaper
# ---------------------------------------------------------------------------

class ChandraFlameshaper(Planeswalker):
    """Chandra, Flameshaper — {5}{R}{R} — 6 loyalty.

    +2: Add {R}{R}{R}. Exile top three cards. May play one this turn.
    +1: Create a token copy of target creature you control (has haste,
        sacrifice at end step).
    −4: Chandra deals 8 damage divided among any number of target
        creatures and/or planeswalkers.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chandra, Flameshaper")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("starting_loyalty", 6)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Chandra"}
        kwargs.setdefault(
            "rules_text",
            "+2: Add {R}{R}{R}. Exile the top three cards of your library. "
            "Choose one. You may play that card this turn.\n"
            "+1: Create a token that's a copy of target creature you control, "
            "except it has haste and \"At the beginning of the end step, "
            "sacrifice this token.\"\n"
            "−4: Chandra deals 8 damage divided as you choose among any number "
            "of target creatures and/or planeswalkers.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus2(game: Any) -> None:
            """Add {R}{R}{R}. Exile top 3, may play one."""
            controller = pw.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 3)
                # Exile top 3 cards (simplified: just exile them)
                # ENGINE LIMITATION: "play until end of turn" from exile not implemented — cards are exiled but cannot be played
                from engine.types import Zone
                library = controller.zones[Zone.LIBRARY]
                for _ in range(min(3, len(library))):
                    cards = library.get_all()
                    if cards:
                        card = cards[-1]  # top of library
                        library.remove(card)
                        exile_zone = controller.zones[Zone.EXILE]
                        exile_zone.add(card)

        def _plus1(game: Any) -> None:
            """Create a token copy of target creature (with haste)."""
            # ENGINE LIMITATION: full copy effect not implemented — token copies basic stats only, missing types/abilities/delayed sacrifice
            from engine.game import create_token
            target = getattr(pw, "_resolve_target", None)
            controller = pw.controller
            if target is not None and controller is not None:
                token = Creature(
                    name=getattr(target, "name", "Token"),
                    base_power=getattr(target, "base_power", 0),
                    base_toughness=getattr(target, "base_toughness", 0),
                    keywords=getattr(target, "keywords", Keyword(0)) | Keyword.HASTE,
                )
                create_token(game, controller, token)

        def _minus4(game: Any) -> None:
            """Deal 8 damage divided among targets."""
            from engine.game import deal_damage
            targets = getattr(pw, "_resolve_targets", None)
            if targets and len(targets) > 0:
                # Divide 8 damage among targets
                damage_per = 8 // len(targets)
                remainder = 8 % len(targets)
                for i, t in enumerate(targets):
                    dmg = damage_per + (1 if i < remainder else 0)
                    deal_damage(game, pw, t, dmg)
            else:
                # Single target fallback
                target = getattr(pw, "_resolve_target", None)
                if target is not None:
                    deal_damage(game, pw, target, 8)

        return [
            LoyaltyAbility(
                loyalty_cost=+2,
                effect=_plus2,
                description="+2: Add {R}{R}{R}. Exile top 3, may play one.",
            ),
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Create a hasty token copy of target creature.",
            ),
            LoyaltyAbility(
                loyalty_cost=-4,
                effect=_minus4,
                description="−4: Deal 8 damage divided among targets.",
            ),
        ]


# ---------------------------------------------------------------------------
# Vivien Reid
# ---------------------------------------------------------------------------

class VivienReid(Planeswalker):
    """Vivien Reid — {3}{G}{G} — 5 loyalty.

    +1: Look at the top four cards. May reveal a creature or land and put
        it into your hand. Rest on bottom.
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
            """Look at top 4 cards, may take a creature or land."""
            import random
            from engine.types import Zone
            controller = pw.controller
            if controller is not None:
                library = controller.zones[Zone.LIBRARY]
                hand = controller.zones[Zone.HAND]
                if len(library) > 0:
                    top_cards = library.get_all()[-4:]
                    found = None
                    # Simplified: take the first creature or land found
                    for card in reversed(top_cards):
                        card_types = getattr(card, "card_types", set())
                        if CardType.CREATURE in card_types or CardType.LAND in card_types:
                            found = card
                            break
                    if found is not None:
                        library.remove(found)
                        hand.add(found)
                        top_cards = [c for c in top_cards if c is not found]
                    # Put remaining looked-at cards on the bottom in random order
                    remaining = [c for c in top_cards if library.contains(c)]
                    for c in remaining:
                        library.remove(c)
                    random.shuffle(remaining)
                    for c in remaining:
                        library.add(c, position="bottom")

        def _minus3(game: Any) -> None:
            """Destroy target artifact, enchantment, or creature with flying."""
            from engine.game import destroy
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                destroy(game, target)

        def _minus8(game: Any) -> None:
            """Emblem — creatures get +2/+2, vigilance, trample, indestructible."""
            # ENGINE LIMITATION: emblem system not implemented — applies one-time buff to current creatures only
            controller = pw.controller
            if controller is not None:
                bf = game.get_battlefield(controller)
                for obj in bf.get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        obj.base_power += 2
                        obj.base_toughness += 2
                        obj.keywords = (
                            getattr(obj, "keywords", Keyword(0))
                            | Keyword.VIGILANCE
                            | Keyword.TRAMPLE
                            | Keyword.INDESTRUCTIBLE
                        )

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Look at top 4, may take creature or land.",
            ),
            LoyaltyAbility(
                loyalty_cost=-3,
                effect=_minus3,
                description="−3: Destroy target artifact, enchantment, or flyer.",
            ),
            LoyaltyAbility(
                loyalty_cost=-8,
                effect=_minus8,
                description="−8: Emblem — +2/+2, vigilance, trample, indestructible.",
            ),
        ]


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_PLANESWALKERS_BATCH2: list[
    tuple[str, type, str, list[str], str, str, str, str, int]
] = [
    ("Kaito, Cunning Infiltrator", KaitoCunningInfiltrator, "{1}{U}{U}",
     ["U"],
     "+1: Target creature can't be blocked. Draw, then discard.\n"
     "−2: Create a 2/1 blue Ninja creature token.\n"
     "−9: Emblem — spell cast → create 2/1 Ninja token.",
     "mythic", "Legendary Planeswalker — Kaito", "44", 3),
    ("Chandra, Flameshaper", ChandraFlameshaper, "{5}{R}{R}",
     ["R"],
     "+2: Add {R}{R}{R}. Exile top 3, may play one.\n"
     "+1: Create a hasty token copy of target creature.\n"
     "−4: Deal 8 damage divided among targets.",
     "mythic", "Legendary Planeswalker — Chandra", "81", 6),
    ("Vivien Reid", VivienReid, "{3}{G}{G}",
     ["G"],
     "+1: Look at top 4, may take creature or land.\n"
     "−3: Destroy target artifact, enchantment, or flyer.\n"
     "−8: Emblem — +2/+2, vigilance, trample, indestructible.",
     "mythic", "Legendary Planeswalker — Vivien", "234", 5),
]


def register_planeswalkers_batch2(registry: CardRegistry) -> None:
    """Register all batch-2 planeswalkers with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number, _loyalty,
    ) in _ALL_PLANESWALKERS_BATCH2:
        metadata = CardMetadata(
            name=card_name,
            mana_cost_str=cost_str,
            type_line=type_line,
            oracle_text=oracle_text,
            power=None,
            toughness=None,
            colors=colors,
            keywords=[],
            rarity=rarity,
            set_code="fdn",
            collector_number=collector_number,
        )
        registry.register(card_name, impl_class, metadata)
