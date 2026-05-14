"""Planeswalker card implementations from Foundations (FDN).

Implements 4 planeswalkers with loyalty abilities:

- **Ajani, Caller of the Pride** — {1}{W}{W}, 4 loyalty.
- **Chandra, Torch of Defiance** — {2}{R}{R}, 4 loyalty.
- **Liliana, Dreadhorde General** — {4}{B}{B}, 6 loyalty.
- **Nissa, Worldwaker** — {3}{G}{G}, 3 loyalty.

Each planeswalker subclasses :class:`~engine.card.Planeswalker` and
overrides :meth:`get_loyalty_abilities` to return its loyalty abilities.

Use :func:`register_planeswalkers` to register all planeswalkers with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Ajani, Caller of the Pride
# ---------------------------------------------------------------------------

class AjaniCallerOfThePride(Planeswalker):
    """Ajani, Caller of the Pride — {1}{W}{W} — 4 loyalty.

    +1: Put a +1/+1 counter on up to one target creature.
    -3: Target creature gains flying and double strike until end of turn.
    -8: Create X 2/2 white Cat creature tokens, where X is your life total.

    (Simplified: abilities are stubs that adjust loyalty only.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ajani, Caller of the Pride")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("starting_loyalty", 4)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ajani"}
        kwargs.setdefault(
            "rules_text",
            "+1: Put a +1/+1 counter on up to one target creature.\n"
            "-3: Target creature gains flying and double strike until end of turn.\n"
            "-8: Create X 2/2 white Cat creature tokens, where X is your life total.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            # Put a +1/+1 counter on up to one target creature.
            target = getattr(pw, "_resolve_target", None)
            if target is not None and hasattr(target, "plus_one_counters"):
                target.plus_one_counters += 1
                target._original_plus_one_counters = target.plus_one_counters

        def _minus3(game: Any) -> None:
            # Target creature gains flying and double strike until end of turn.
            target = getattr(pw, "_resolve_target", None)
            if target is not None and hasattr(target, "keywords"):
                from engine.types import Keyword
                target.keywords = target.keywords | Keyword.FLYING | Keyword.DOUBLE_STRIKE

        def _minus8(game: Any) -> None:
            # Create X 2/2 white Cat creature tokens, where X is your life total.
            controller = pw.controller
            if controller is not None:
                from engine.card import Creature
                from engine.game import create_token
                life = getattr(controller, "life", 0)
                for _ in range(max(0, life)):
                    token = Creature(name="Cat", base_power=2, base_toughness=2)
                    create_token(game, controller, token)

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Put a +1/+1 counter on up to one target creature."),
            LoyaltyAbility(loyalty_cost=-3, effect=_minus3, description="-3: Target creature gains flying and double strike until end of turn."),
            LoyaltyAbility(loyalty_cost=-8, effect=_minus8, description="-8: Create X 2/2 Cat tokens, where X is your life total."),
        ]


# ---------------------------------------------------------------------------
# Chandra, Torch of Defiance
# ---------------------------------------------------------------------------

class ChandraTorchOfDefiance(Planeswalker):
    """Chandra, Torch of Defiance — {2}{R}{R} — 4 loyalty.

    +1: Exile the top card of your library. You may cast that card.
        If you don't, Chandra deals 2 damage to each opponent.
    +1: Add {R}{R}.
    -3: Chandra deals 4 damage to target creature.
    -7: You get an emblem with "Whenever you cast a spell, this emblem
        deals 5 damage to any target."

    (Simplified: abilities are stubs that adjust loyalty only.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chandra, Torch of Defiance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{R}"))
        kwargs.setdefault("starting_loyalty", 4)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Chandra"}
        kwargs.setdefault(
            "rules_text",
            "+1: Exile top card, may cast or deal 2 to opponents.\n"
            "+1: Add {R}{R}.\n"
            "-3: Deal 4 damage to target creature.\n"
            "-7: Emblem — whenever you cast a spell, deal 5 to any target.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_exile(game: Any) -> None:
            # Exile top card, may cast or deal 2 to opponents.
            from engine.game import deal_damage
            controller = pw.controller
            if controller is not None:
                # Simplified: deal 2 damage to each opponent
                for p in game.players:
                    if p is not controller:
                        deal_damage(game, pw, p, 2)

        def _plus1_mana(game: Any) -> None:
            # Add {R}{R}.
            controller = pw.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 2)

        def _minus3(game: Any) -> None:
            # Deal 4 damage to target creature.
            from engine.game import deal_damage
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                deal_damage(game, pw, target, 4)

        def _minus7(game: Any) -> None:
            # Emblem — deal 5 on spell cast (simplified: no-op emblem stub).
            pass

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_exile, description="+1: Exile top card, may cast or deal 2."),
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_mana, description="+1: Add {R}{R}."),
            LoyaltyAbility(loyalty_cost=-3, effect=_minus3, description="-3: Deal 4 damage to target creature."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="-7: Emblem — deal 5 on spell cast."),
        ]


# ---------------------------------------------------------------------------
# Liliana, Dreadhorde General
# ---------------------------------------------------------------------------

class LilianaDreadhordeGeneral(Planeswalker):
    """Liliana, Dreadhorde General — {4}{B}{B} — 6 loyalty.

    +1: Each opponent sacrifices a creature.
    -4: Each player draws cards equal to the number of creatures they control,
        then each opponent discards that many cards.
    -9: Each opponent chooses a permanent they control of each permanent type
        and sacrifices the rest.

    (Simplified: abilities are stubs that adjust loyalty only.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Liliana, Dreadhorde General")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 6)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Liliana"}
        kwargs.setdefault(
            "rules_text",
            "+1: Each opponent sacrifices a creature.\n"
            "-4: Each player draws cards equal to creatures they control, "
            "then each opponent discards that many.\n"
            "-9: Each opponent keeps one of each permanent type, sacrifices the rest.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            # Each opponent sacrifices a creature.
            from engine.game import sacrifice
            for p in game.players:
                if p is not pw.controller:
                    from engine.types import CardType as CT
                    bf = game.get_battlefield(p)
                    for obj in bf.get_all():
                        if CT.CREATURE in getattr(obj, "card_types", set()):
                            sacrifice(game, p, obj)
                            break

        def _minus4(game: Any) -> None:
            # Each player draws cards equal to creatures they control.
            from engine.game import draw_card
            from engine.types import CardType as CT
            for p in game.players:
                bf = game.get_battlefield(p)
                count = sum(1 for obj in bf.get_all() if CT.CREATURE in getattr(obj, "card_types", set()))
                for _ in range(count):
                    draw_card(game, p)

        def _minus9(game: Any) -> None:
            # Opponents keep one of each permanent type, sacrifice rest (simplified stub).
            pass

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Each opponent sacrifices a creature."),
            LoyaltyAbility(loyalty_cost=-4, effect=_minus4, description="-4: Draw/discard based on creatures."),
            LoyaltyAbility(loyalty_cost=-9, effect=_minus9, description="-9: Opponents keep one of each type, sacrifice rest."),
        ]


# ---------------------------------------------------------------------------
# Nissa, Worldwaker
# ---------------------------------------------------------------------------

class NissaWorldwaker(Planeswalker):
    """Nissa, Worldwaker — {3}{G}{G} — 3 loyalty.

    +1: Target land you control becomes a 4/4 Elemental creature with trample.
        It's still a land.
    +1: Untap up to four target Forests.
    -7: Search your library for any number of basic land cards, put them onto
        the battlefield, then shuffle your library. Those lands become 4/4
        Elemental creatures with trample. They're still lands.

    (Simplified: abilities are stubs that adjust loyalty only.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Nissa, Worldwaker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Nissa"}
        kwargs.setdefault(
            "rules_text",
            "+1: Target land becomes a 4/4 Elemental with trample.\n"
            "+1: Untap up to four target Forests.\n"
            "-7: Search for basics, put onto battlefield as 4/4 Elementals.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_animate(game: Any) -> None:
            # Target land becomes a 4/4 Elemental with trample (simplified).
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                target.base_power = 4
                target.base_toughness = 4

        def _plus1_untap(game: Any) -> None:
            # Untap up to four Forests (simplified: untap up to 4 lands).
            controller = pw.controller
            if controller is not None:
                bf = game.get_battlefield(controller)
                untapped = 0
                for obj in bf.get_all():
                    if untapped >= 4:
                        break
                    if getattr(obj, "is_tapped", False):
                        obj.is_tapped = False
                        untapped += 1

        def _minus7(game: Any) -> None:
            # Search for basics, make 4/4 Elementals (simplified stub).
            pass

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_animate, description="+1: Animate a land as 4/4 Elemental."),
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_untap, description="+1: Untap up to four Forests."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="-7: Search for basics, make 4/4 Elementals."),
        ]


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_PLANESWALKERS: list[
    tuple[str, type, str, list[str], str, str, str, str, int]
] = [
    ("Ajani, Caller of the Pride", AjaniCallerOfThePride, "{1}{W}{W}",
     ["W"],
     "+1: Put a +1/+1 counter on up to one target creature.\n"
     "-3: Target creature gains flying and double strike until end of turn.\n"
     "-8: Create X 2/2 white Cat creature tokens, where X is your life total.",
     "mythic", "Legendary Planeswalker — Ajani", "", 4),
    ("Chandra, Torch of Defiance", ChandraTorchOfDefiance, "{2}{R}{R}",
     ["R"],
     "+1: Exile top card, may cast or deal 2 to opponents.\n"
     "+1: Add {R}{R}.\n"
     "-3: Deal 4 damage to target creature.\n"
     "-7: Emblem — whenever you cast a spell, deal 5 to any target.",
     "mythic", "Legendary Planeswalker — Chandra", "", 4),
    ("Liliana, Dreadhorde General", LilianaDreadhordeGeneral, "{4}{B}{B}",
     ["B"],
     "+1: Each opponent sacrifices a creature.\n"
     "-4: Draw/discard based on creatures.\n"
     "-9: Opponents keep one of each type, sacrifice rest.",
     "mythic", "Legendary Planeswalker — Liliana", "", 6),
    ("Nissa, Worldwaker", NissaWorldwaker, "{3}{G}{G}",
     ["G"],
     "+1: Animate a land as 4/4 Elemental.\n"
     "+1: Untap up to four Forests.\n"
     "-7: Search for basics, make 4/4 Elementals.",
     "mythic", "Legendary Planeswalker — Nissa", "", 3),
]


def register_planeswalkers(registry: CardRegistry) -> None:
    """Register all planeswalkers with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number, _loyalty,
    ) in _ALL_PLANESWALKERS:
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
