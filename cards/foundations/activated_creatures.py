"""Batch 9 — FDN creatures with activated abilities.

Implements 17 real FDN creatures whose primary mechanic is an activated
ability: tap abilities, sacrifice abilities, mana abilities on creatures,
and pump abilities.

Each creature subclasses :class:`~engine.card.Creature` (or
:class:`~engine.card.ArtifactCreature` for artifact creatures) and
overrides :meth:`get_activated_abilities` to return
:class:`~engine.card.ActivatedAbility` objects.  Some creatures also
override :meth:`get_mana_abilities` for mana-producing tap abilities.

All cards are verified against Scryfall FDN data with correct collector
numbers.

Use :func:`register_activated_creatures` to register all cards with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


# ===================================================================
# MANA ABILITIES ON CREATURES
# ===================================================================


class LlanowarElves(Creature):
    """Llanowar Elves — {G} — 1/1 — Elf Druid

    {T}: Add {G}.

    FDN collector number 227.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Llanowar Elves")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("rules_text", "{T}: Add {G}.")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.GREEN, 1)

        return [ManaAbility(
            cost=_tap_cost,
            mana_produced=_effect,
            description="{T}: Add {G}.",
        )]


class ElvishArchdruid(Creature):
    """Elvish Archdruid — {1}{G}{G} — 2/2 — Elf Druid

    Other Elf creatures you control get +1/+1.
    {T}: Add {G} for each Elf you control.

    FDN collector number 219.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elvish Archdruid")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Other Elf creatures you control get +1/+1.\n"
            "{T}: Add {G} for each Elf you control.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            # Count Elves you control (including self)
            elf_count = 0
            bf = game.get_battlefield(controller)
            for card in bf.get_all():
                if (
                    CardType.CREATURE in getattr(card, "card_types", set())
                    and "Elf" in getattr(card, "subtypes", set())
                ):
                    elf_count += 1
            if elf_count > 0:
                controller.mana_pool.add(ManaType.GREEN, elf_count)

        return [ManaAbility(
            cost=_tap_cost,
            mana_produced=_effect,
            description="{T}: Add {G} for each Elf you control.",
        )]

    def register_triggers(self, game: Any) -> None:
        """Register the static +1/+1 lord effect for other Elves.

        # ENGINE LIMITATION: Static abilities should use the continuous effect
        # layer system. This simplified version applies immediately on ETB.
        """
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_PERMANENT,
            Layer,
            SubLayer,
        )

        source = self

        def _apply(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, source):
                return
            bf = game.get_battlefield(controller)
            for card in bf.get_all():
                if card is source:
                    continue
                if (
                    CardType.CREATURE in getattr(card, "card_types", set())
                    and "Elf" in getattr(card, "subtypes", set())
                ):
                    card.base_power = getattr(card, "_original_base_power", card.base_power) + 1
                    card.base_toughness = getattr(card, "_original_base_toughness", card.base_toughness) + 1

        effect = ContinuousEffect(
            source=source,
            apply_fn=_apply,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFICATION,
            duration=DURATION_PERMANENT,
        )
        game.effect_manager.register(effect)


class RubyDaringTracker(Creature):
    """Ruby, Daring Tracker — {R}{G} — 1/2 — Human Scout

    Haste
    Whenever Ruby attacks while you control a creature with power 4 or
    greater, Ruby gets +2/+2 until end of turn.
    {T}: Add {R} or {G}.

    FDN collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ruby, Daring Tracker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{G}"))
        kwargs.setdefault("subtypes", {"Human", "Scout"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Haste\nWhenever Ruby attacks while you control a creature with "
            "power 4 or greater, Ruby gets +2/+2 until end of turn.\n"
            "{T}: Add {R} or {G}.",
        )
        super().__init__(**kwargs)

    # ENGINE LIMITATION: attack trigger (+2/+2 when attacking with 4+ power creature) not implemented — requires attack event tracking

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _make_effect(mtype: ManaType):
            def _effect(game: Any) -> None:
                controller = source.controller
                if controller is not None:
                    controller.mana_pool.add(mtype, 1)
            return _effect

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_make_effect(ManaType.RED),
                description="{T}: Add {R}.",
            ),
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_make_effect(ManaType.GREEN),
                description="{T}: Add {G}.",
            ),
        ]


# ===================================================================
# TAP ABILITIES
# ===================================================================


class RuneSealedWall(ArtifactCreature):
    """Rune-Sealed Wall — {2}{U} — 0/6 — Wall

    Defender
    {T}: Surveil 1.

    FDN collector number 49.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rune-Sealed Wall")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Wall"})
        kwargs.setdefault("keywords", Keyword.DEFENDER)
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Defender\n{T}: Surveil 1.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return _tap_cost(game, src)

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            if len(library) > 0:
                card = library.top(1)[0]
                library.remove(card)
                # Surveil: may put into graveyard (simplified: always
                # put into graveyard for deterministic behaviour).
                graveyard = controller.zones[Zone.GRAVEYARD]
                graveyard.add(card)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}: Surveil 1.",
        )]


class StrixLookout(Creature):
    """Strix Lookout — {1}{U} — 1/2 — Bird

    Flying, vigilance
    {1}{U}, {T}: Draw a card, then discard a card.

    FDN collector number 52.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Strix Lookout")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Bird"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n{1}{U}, {T}: Draw a card, then discard a card.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 2:
                return False
            controller.mana_pool.pay(ManaCost.parse("{1}{U}"))
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import draw_card, discard

            controller = source.controller
            if controller is None:
                return
            drawn = draw_card(game, controller)
            # Discard a card (simplified: discard the drawn card if any,
            # or the last card in hand)
            hand = controller.zones[Zone.HAND]
            if len(hand) > 0:
                to_discard = hand.cards[-1] if hasattr(hand, "cards") else hand.get_all()[-1]
                discard(game, controller, to_discard)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}{U}, {T}: Draw a card, then discard a card.",
        )]


class AxgardCavalry(Creature):
    """Axgard Cavalry — {1}{R} — 2/2 — Dwarf Berserker

    {T}: Target creature gains haste until end of turn.

    FDN collector number 189.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Axgard Cavalry")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Berserker"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{T}: Target creature gains haste until end of turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return _tap_cost(game, src)

        def _effect(game: Any) -> None:
            target = getattr(source, "_current_target", None)
            if target is not None:
                target.summoning_sick = False
                # Add haste keyword
                kw = getattr(target, "keywords", Keyword(0))
                target.keywords = kw | Keyword.HASTE

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}: Target creature gains haste until end of turn.",
        )]


class KrenkoMobBoss(Creature):
    """Krenko, Mob Boss — {2}{R}{R} — 3/3 — Goblin Warrior

    {T}: Create X 1/1 red Goblin creature tokens, where X is the number
    of Goblins you control.

    FDN collector number 204.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Krenko, Mob Boss")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Warrior"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "{T}: Create X 1/1 red Goblin creature tokens, where X is "
            "the number of Goblins you control.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return _tap_cost(game, src)

        def _effect(game: Any) -> None:
            from engine.game import create_token

            controller = source.controller
            if controller is None:
                return
            # Count Goblins you control
            goblin_count = 0
            bf = game.get_battlefield(controller)
            for card in bf.get_all():
                if "Goblin" in getattr(card, "subtypes", set()):
                    goblin_count += 1
            for _ in range(goblin_count):
                token = Creature(
                    name="Goblin",
                    base_power=1,
                    base_toughness=1,
                    subtypes={"Goblin"},
                )
                token.is_token = True
                create_token(game, controller, token)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}: Create X 1/1 red Goblin creature tokens, "
            "where X is the number of Goblins you control.",
        )]


# ===================================================================
# SACRIFICE ABILITIES
# ===================================================================


class CatharCommando(Creature):
    """Cathar Commando — {1}{W} — 3/1 — Human Soldier

    Flash
    {1}, Sacrifice this creature: Destroy target artifact or enchantment.

    FDN collector number 139.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cathar Commando")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Soldier"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\n{1}, Sacrifice this creature: Destroy target artifact "
            "or enchantment.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 1:
                return False
            controller.mana_pool.pay(ManaCost(generic=1))
            # Sacrifice self
            from engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            from engine.game import destroy

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            if not _is_on_battlefield(game, target):
                return
            # Only targets artifacts or enchantments
            target_types = getattr(target, "card_types", set())
            if CardType.ARTIFACT in target_types or CardType.ENCHANTMENT in target_types:
                destroy(game, target)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}, Sacrifice this creature: Destroy target "
            "artifact or enchantment.",
        )]


class FanaticalFirebrand(Creature):
    """Fanatical Firebrand — {R} — 1/1 — Goblin Pirate

    Haste
    {T}, Sacrifice this creature: It deals 1 damage to any target.

    FDN collector number 195.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fanatical Firebrand")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Pirate"})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Haste\n{T}, Sacrifice this creature: It deals 1 damage to "
            "any target.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            # Sacrifice self
            controller = src.controller
            if controller is None:
                return False
            from engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            from engine.game import deal_damage

            target = getattr(source, "_current_target", None)
            if target is not None:
                deal_damage(game, source, target, 1)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}, Sacrifice this creature: It deals 1 damage "
            "to any target.",
        )]


class HeartfireImmolator(Creature):
    """Heartfire Immolator — {1}{R} — 2/2 — Human Wizard

    Prowess
    {R}, Sacrifice this creature: It deals damage equal to its power to
    target creature or planeswalker.

    FDN collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heartfire Immolator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.PROWESS)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Prowess\n{R}, Sacrifice this creature: It deals damage equal "
            "to its power to target creature or planeswalker.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            # Pay {R}
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{R}"))
            # Snapshot power before sacrifice (last known information)
            src._snapshot_power = getattr(src, "power", src.base_power)
            # Sacrifice self
            from engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            from engine.game import deal_damage

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            # Use last-known power (snapshotted during cost payment)
            dmg = getattr(source, "_snapshot_power", source.base_power)
            deal_damage(game, source, target, dmg)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{R}, Sacrifice this creature: It deals damage "
            "equal to its power to target creature or planeswalker.",
        )]


class BurnishedHart(ArtifactCreature):
    """Burnished Hart — {3} — 2/2 — Elk

    {3}, Sacrifice this creature: Search your library for up to two basic
    land cards, put them onto the battlefield tapped, then shuffle.

    FDN collector number 250.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burnished Hart")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", {"Elk"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{3}, Sacrifice this creature: Search your library for up to "
            "two basic land cards, put them onto the battlefield tapped, "
            "then shuffle.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 3:
                return False
            controller.mana_pool.pay(ManaCost(generic=3))
            # Sacrifice self
            from engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            found: list[Any] = []
            for card in list(library.get_all()):
                if getattr(card, "is_basic_land", False) and len(found) < 2:
                    found.append(card)
            for basic in found:
                library.remove(basic)
                basic.is_tapped = True
                basic.controller = controller
                bf = game.get_battlefield(controller)
                bf.add(basic)
            if len(library) > 0:
                library.shuffle()

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{3}, Sacrifice this creature: Search your library "
            "for up to two basic land cards, put them onto the battlefield "
            "tapped, then shuffle.",
        )]


class HungryGhoul(Creature):
    """Hungry Ghoul — {1}{B} — 2/2 — Zombie

    {1}, Sacrifice another creature: Put a +1/+1 counter on this creature.

    FDN collector number 62.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hungry Ghoul")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{1}, Sacrifice another creature: Put a +1/+1 counter on "
            "this creature.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 1:
                return False
            # Need a target creature to sacrifice (another creature you control)
            sac_target = getattr(src, "_sacrifice_target", None)
            if sac_target is None or sac_target is src:
                return False
            if not _is_on_battlefield(game, sac_target):
                return False
            if getattr(sac_target, "controller", None) is not controller:
                return False
            controller.mana_pool.pay(ManaCost(generic=1))
            from engine.game import sacrifice
            sacrifice(game, controller, sac_target)
            return True

        def _effect(game: Any) -> None:
            from engine.game import add_counter
            if _is_on_battlefield(game, source):
                add_counter(game, source, "+1/+1", 1)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}, Sacrifice another creature: Put a +1/+1 "
            "counter on this creature.",
        )]


# ===================================================================
# PUMP ABILITIES
# ===================================================================


class ShivanDragon(Creature):
    """Shivan Dragon — {4}{R}{R} — 5/5 — Dragon

    Flying
    {R}: This creature gets +1/+0 until end of turn.

    FDN collector number 206.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Shivan Dragon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{R}"))
        kwargs.setdefault("subtypes", {"Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying\n{R}: This creature gets +1/+0 until end of turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{R}"))
            return True

        # ENGINE LIMITATION: pump modifies base_power; no end-of-turn cleanup mechanism in engine
        def _effect(game: Any) -> None:
            # +1/+0 until end of turn — boost base_power
            source.base_power += 1

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{R}: This creature gets +1/+0 until end of turn.",
        )]


class SowerOfChaos(Creature):
    """Sower of Chaos — {3}{R} — 4/3 — Devil

    {2}{R}: Target creature can't block this turn.

    FDN collector number 95.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sower of Chaos")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("subtypes", {"Devil"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "{2}{R}: Target creature can't block this turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 3:
                return False
            # Need at least 1 red
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{2}{R}"))
            return True

        def _effect(game: Any) -> None:
            target = getattr(source, "_current_target", None)
            if target is not None:
                target._cant_block = True

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{R}: Target creature can't block this turn.",
        )]


class TreetopSnarespinner(Creature):
    """Treetop Snarespinner — {3}{G} — 1/4 — Spider

    Reach
    Deathtouch
    {2}{G}: Put a +1/+1 counter on target creature you control. Activate
    only as a sorcery.

    FDN collector number 114.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Treetop Snarespinner")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("subtypes", {"Spider"})
        kwargs.setdefault("keywords", Keyword.REACH | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Reach\nDeathtouch\n{2}{G}: Put a +1/+1 counter on target "
            "creature you control. Activate only as a sorcery.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 3:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{2}{G}"))
            return True

        # ENGINE LIMITATION: sorcery-speed timing not enforced
        def _effect(game: Any) -> None:
            from engine.game import add_counter

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            # Must target a creature you control
            controller = source.controller
            if getattr(target, "controller", None) is not controller:
                return
            if _is_on_battlefield(game, target):
                add_counter(game, target, "+1/+1", 1)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{G}: Put a +1/+1 counter on target creature "
            "you control. Activate only as a sorcery.",
        )]


# ===================================================================
# OTHER ACTIVATED ABILITIES
# ===================================================================


class SpectralSailor(Creature):
    """Spectral Sailor — {U} — 1/1 — Spirit Pirate

    Flash
    Flying
    {3}{U}: Draw a card.

    FDN collector number 164.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spectral Sailor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", {"Spirit", "Pirate"})
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\nFlying\n{3}{U}: Draw a card.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 4:
                return False
            if controller.mana_pool.get(ManaType.BLUE) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{3}{U}"))
            return True

        def _effect(game: Any) -> None:
            from engine.game import draw_card

            controller = source.controller
            if controller is not None:
                draw_card(game, controller)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{3}{U}: Draw a card.",
        )]


class ScavengingOoze(Creature):
    """Scavenging Ooze — {1}{G} — 2/2 — Ooze

    {G}: Exile target card from a graveyard. If it was a creature card,
    put a +1/+1 counter on this creature and you gain 1 life.

    FDN collector number 232.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scavenging Ooze")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Ooze"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{G}: Exile target card from a graveyard. If it was a creature "
            "card, put a +1/+1 counter on this creature and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{G}"))
            return True

        def _effect(game: Any) -> None:
            from engine.game import add_counter, exile

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            # Check if target is a creature card
            is_creature = CardType.CREATURE in getattr(target, "card_types", set())
            # Exile the target card from the graveyard
            exile(game, target)
            # If it was a creature card, +1/+1 counter and gain 1 life
            if is_creature and _is_on_battlefield(game, source):
                add_counter(game, source, "+1/+1", 1)
                controller = source.controller
                if controller is not None:
                    controller.life += 1

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{G}: Exile target card from a graveyard. If it "
            "was a creature card, put a +1/+1 counter on this creature "
            "and you gain 1 life.",
        )]


class ReassemblingSkeleton(Creature):
    """Reassembling Skeleton — {1}{B} — 1/1 — Skeleton Warrior

    {1}{B}: Return this card from your graveyard to the battlefield tapped.

    FDN collector number 182.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Reassembling Skeleton")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Skeleton", "Warrior"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "{1}{B}: Return this card from your graveyard to the "
            "battlefield tapped.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            # Can only be activated from the graveyard
            controller = src.owner  # use owner since controller may be None
            if controller is None:
                return False
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(src):
                return False
            if controller.mana_pool.total() < 2:
                return False
            if controller.mana_pool.get(ManaType.BLACK) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{1}{B}"))
            return True

        def _effect(game: Any) -> None:
            controller = source.owner
            if controller is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(source):
                return
            graveyard.remove(source)
            source.controller = controller
            source.is_tapped = True
            source.damage_marked = 0
            source.summoning_sick = True
            # Clear accumulated state — return as fresh creature
            source.plus_one_counters = 0
            if hasattr(source, "counters"):
                source.counters.clear()
            bf = game.get_battlefield(controller)
            bf.add(source)
            # Register triggers
            if hasattr(source, "register_triggers"):
                source.register_triggers(game)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}{B}: Return this card from your graveyard to "
            "the battlefield tapped.",
        )]


class MildManneredLibrarian(Creature):
    """Mild-Mannered Librarian — {G} — 1/1 — Human Werewolf

    {3}{G}: This creature becomes a Werewolf. Put two +1/+1 counters on
    it and you draw a card. Activate only once.

    FDN collector number 228.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mild-Mannered Librarian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault("subtypes", {"Human", "Werewolf"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "{3}{G}: This creature becomes a Werewolf. Put two +1/+1 "
            "counters on it and you draw a card. Activate only once.",
        )
        super().__init__(**kwargs)
        self._librarian_activated = False

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if source._librarian_activated:
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 4:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{3}{G}"))
            source._librarian_activated = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import add_counter, draw_card

            # Becomes a Werewolf (add subtype, remove Human)
            source.subtypes.discard("Human")
            source.subtypes.add("Werewolf")
            # Put two +1/+1 counters
            add_counter(game, source, "+1/+1", 2)
            # Draw a card
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{3}{G}: This creature becomes a Werewolf. Put "
            "two +1/+1 counters on it and you draw a card. Activate "
            "only once.",
        )]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

_ACTIVATED_CREATURE_CARDS: list[
    tuple[str, type[Creature], str, str, str, str | None, str | None, list[str], list[str], str]
] = [
    # (name, class, collector_number, type_line, oracle_text, power, toughness,
    #  colors, keywords, rarity)
    (
        "Llanowar Elves", LlanowarElves, "227",
        "Creature — Elf Druid",
        "{T}: Add {G}.",
        "1", "1", ["G"], [], "common",
    ),
    (
        "Elvish Archdruid", ElvishArchdruid, "219",
        "Creature — Elf Druid",
        "Other Elf creatures you control get +1/+1.\n{T}: Add {G} for each Elf you control.",
        "2", "2", ["G"], [], "rare",
    ),
    (
        "Ruby, Daring Tracker", RubyDaringTracker, "245",
        "Legendary Creature — Human Scout",
        "Haste\nWhenever Ruby attacks while you control a creature with power 4 or greater, Ruby gets +2/+2 until end of turn.\n{T}: Add {R} or {G}.",
        "1", "2", ["G", "R"], ["Haste"], "uncommon",
    ),
    (
        "Rune-Sealed Wall", RuneSealedWall, "49",
        "Artifact Creature — Wall",
        "Defender\n{T}: Surveil 1.",
        "0", "6", ["U"], ["Surveil", "Defender"], "uncommon",
    ),
    (
        "Strix Lookout", StrixLookout, "52",
        "Creature — Bird",
        "Flying, vigilance\n{1}{U}, {T}: Draw a card, then discard a card.",
        "1", "2", ["U"], ["Flying", "Vigilance"], "common",
    ),
    (
        "Axgard Cavalry", AxgardCavalry, "189",
        "Creature — Dwarf Berserker",
        "{T}: Target creature gains haste until end of turn.",
        "2", "2", ["R"], [], "common",
    ),
    (
        "Krenko, Mob Boss", KrenkoMobBoss, "204",
        "Legendary Creature — Goblin Warrior",
        "{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins you control.",
        "3", "3", ["R"], [], "rare",
    ),
    (
        "Cathar Commando", CatharCommando, "139",
        "Creature — Human Soldier",
        "Flash\n{1}, Sacrifice this creature: Destroy target artifact or enchantment.",
        "3", "1", ["W"], ["Flash"], "common",
    ),
    (
        "Fanatical Firebrand", FanaticalFirebrand, "195",
        "Creature — Goblin Pirate",
        "Haste\n{T}, Sacrifice this creature: It deals 1 damage to any target.",
        "1", "1", ["R"], ["Haste"], "common",
    ),
    (
        "Heartfire Immolator", HeartfireImmolator, "201",
        "Creature — Human Wizard",
        "Prowess\n{R}, Sacrifice this creature: It deals damage equal to its power to target creature or planeswalker.",
        "2", "2", ["R"], ["Prowess"], "uncommon",
    ),
    (
        "Burnished Hart", BurnishedHart, "250",
        "Artifact Creature — Elk",
        "{3}, Sacrifice this creature: Search your library for up to two basic land cards, put them onto the battlefield tapped, then shuffle.",
        "2", "2", [], [], "uncommon",
    ),
    (
        "Hungry Ghoul", HungryGhoul, "62",
        "Creature — Zombie",
        "{1}, Sacrifice another creature: Put a +1/+1 counter on this creature.",
        "2", "2", ["B"], [], "common",
    ),
    (
        "Shivan Dragon", ShivanDragon, "206",
        "Creature — Dragon",
        "Flying\n{R}: This creature gets +1/+0 until end of turn.",
        "5", "5", ["R"], ["Flying"], "uncommon",
    ),
    (
        "Sower of Chaos", SowerOfChaos, "95",
        "Creature — Devil",
        "{2}{R}: Target creature can't block this turn.",
        "4", "3", ["R"], [], "common",
    ),
    (
        "Treetop Snarespinner", TreetopSnarespinner, "114",
        "Creature — Spider",
        "Reach\nDeathtouch\n{2}{G}: Put a +1/+1 counter on target creature you control. Activate only as a sorcery.",
        "1", "4", ["G"], ["Reach", "Deathtouch"], "common",
    ),
    (
        "Spectral Sailor", SpectralSailor, "164",
        "Creature — Spirit Pirate",
        "Flash\nFlying\n{3}{U}: Draw a card.",
        "1", "1", ["U"], ["Flash", "Flying"], "uncommon",
    ),
    (
        "Scavenging Ooze", ScavengingOoze, "232",
        "Creature — Ooze",
        "{G}: Exile target card from a graveyard. If it was a creature card, put a +1/+1 counter on this creature and you gain 1 life.",
        "2", "2", ["G"], [], "rare",
    ),
    (
        "Reassembling Skeleton", ReassemblingSkeleton, "182",
        "Creature — Skeleton Warrior",
        "{1}{B}: Return this card from your graveyard to the battlefield tapped.",
        "1", "1", ["B"], [], "uncommon",
    ),
    (
        "Mild-Mannered Librarian", MildManneredLibrarian, "228",
        "Creature — Human Werewolf",
        "{3}{G}: This creature becomes a Werewolf. Put two +1/+1 counters on it and you draw a card. Activate only once.",
        "1", "1", ["G"], [], "uncommon",
    ),
]


def register_activated_creatures(registry: CardRegistry) -> None:
    """Register all FDN activated-ability creatures with *registry*."""
    from cards.registry import CardMetadata

    for (
        name, impl_class, collector_number, type_line, oracle_text,
        power, toughness, colors, keywords, rarity,
    ) in _ACTIVATED_CREATURE_CARDS:
        metadata = CardMetadata(
            name=name,
            mana_cost_str="",
            type_line=type_line,
            oracle_text=oracle_text,
            power=power,
            toughness=toughness,
            colors=colors,
            keywords=keywords,
            rarity=rarity,
            set_code="fdn",
            collector_number=collector_number,
        )
        registry.register(name, impl_class, metadata)
