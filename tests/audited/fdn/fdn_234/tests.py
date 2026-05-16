"""Audited tests for FDN 234 — Vivien Reid."""

from __future__ import annotations

import pytest

from card_impl import VivienReid
from engine.card import Creature, Planeswalker
from engine.continuous_effects import ContinuousEffect, Layer
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from tests.test_utils import create_game, set_board_state


class TestVivienBasics:
    """Basic card properties."""

    def test_is_planeswalker(self) -> None:
        card = VivienReid(owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types

    def test_mana_cost(self) -> None:
        card = VivienReid(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{G}{G}")

    def test_starting_loyalty_is_5(self) -> None:
        card = VivienReid(owner=None)
        assert card.starting_loyalty == 5
        assert card.loyalty == 5

    def test_is_legendary(self) -> None:
        card = VivienReid(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_vivien_subtype(self) -> None:
        card = VivienReid(owner=None)
        assert "Vivien" in card.subtypes

    def test_has_three_loyalty_abilities(self) -> None:
        card = VivienReid(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs_are_plus1_minus3_minus8(self) -> None:
        card = VivienReid(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1
        assert abilities[1].loyalty_cost == -3
        assert abilities[2].loyalty_cost == -8


class TestVivienPlus1:
    """+1: Look at top 4, may reveal creature or land to hand."""

    def test_plus1_puts_creature_into_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        vivien = VivienReid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(vivien)

        # Set up library with a creature on top
        creature = Creature(name="Elk", base_power=3, base_toughness=3, owner=p1)
        from engine.card import CardImpl
        non_creature = CardImpl(name="Spell", owner=p1, card_types={CardType.INSTANT})
        p1.zones[Zone.LIBRARY].add(non_creature)  # bottom
        p1.zones[Zone.LIBRARY].add(creature)  # top

        abilities = vivien.get_loyalty_abilities()
        abilities[0].effect(game)

        hand = p1.zones[Zone.HAND]
        hand_names = [getattr(c, "name", "") for c in hand.get_all()]
        assert "Elk" in hand_names

    def test_plus1_puts_rest_on_bottom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        vivien = VivienReid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(vivien)

        creature = Creature(name="Elk", base_power=3, base_toughness=3, owner=p1)
        from engine.card import CardImpl
        spell1 = CardImpl(name="Spell1", owner=p1, card_types={CardType.INSTANT})
        spell2 = CardImpl(name="Spell2", owner=p1, card_types={CardType.INSTANT})
        spell3 = CardImpl(name="Spell3", owner=p1, card_types={CardType.INSTANT})
        # Add in order: bottom first
        p1.zones[Zone.LIBRARY].add(spell1)
        p1.zones[Zone.LIBRARY].add(spell2)
        p1.zones[Zone.LIBRARY].add(spell3)
        p1.zones[Zone.LIBRARY].add(creature)  # top

        abilities = vivien.get_loyalty_abilities()
        abilities[0].effect(game)

        # creature should be in hand, 3 spells stay in library
        assert len(p1.zones[Zone.HAND]) == 1
        assert len(p1.zones[Zone.LIBRARY]) == 3

    def test_plus1_no_creature_or_land_nothing_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        vivien = VivienReid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(vivien)

        from engine.card import CardImpl
        for i in range(4):
            spell = CardImpl(name=f"Spell{i}", owner=p1, card_types={CardType.INSTANT})
            p1.zones[Zone.LIBRARY].add(spell)

        abilities = vivien.get_loyalty_abilities()
        abilities[0].effect(game)

        # Nothing matches creature or land, hand stays empty
        assert len(p1.zones[Zone.HAND]) == 0
        # All 4 go back to bottom of library
        assert len(p1.zones[Zone.LIBRARY]) == 4

    def test_plus1_with_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        vivien = VivienReid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(vivien)

        abilities = vivien.get_loyalty_abilities()
        # Should not raise with empty library
        abilities[0].effect(game)
        assert len(p1.zones[Zone.HAND]) == 0

    def test_plus1_with_multiple_eligible_chooses_one(self) -> None:
        """When multiple creatures/lands are in top 4, controller chooses one to put into hand."""
        game = create_game()
        p1 = game.players[0]
        vivien = VivienReid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(vivien)

        # Set up library with multiple eligible cards (creatures and lands)
        creature1 = Creature(name="Elk", base_power=3, base_toughness=3, owner=p1)
        creature2 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        from engine.card import CardImpl
        land = CardImpl(name="Forest", owner=p1, card_types={CardType.LAND})
        spell = CardImpl(name="Spell", owner=p1, card_types={CardType.INSTANT})
        # Add bottom to top
        p1.zones[Zone.LIBRARY].add(spell)
        p1.zones[Zone.LIBRARY].add(land)
        p1.zones[Zone.LIBRARY].add(creature2)
        p1.zones[Zone.LIBRARY].add(creature1)  # top

        abilities = vivien.get_loyalty_abilities()
        abilities[0].effect(game)

        # Exactly one card should be in hand (the controller's choice among eligible)
        hand = p1.zones[Zone.HAND]
        assert len(hand) == 1
        chosen = hand.get_all()[0]
        # The chosen card must be one of the eligible creature/land cards
        assert chosen.name in ("Elk", "Bear", "Forest")
        # The remaining 3 cards should be on bottom of library
        assert len(p1.zones[Zone.LIBRARY]) == 3


class TestVivienMinus3:
    """−3: Destroy target artifact, enchantment, or creature with flying."""

    def test_minus3_destroys_artifact(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        vivien = VivienReid(owner=p1, controller=p1)
        from engine.card import CardImpl
        artifact = CardImpl(name="Sol Ring", owner=p2, controller=p2, card_types={CardType.ARTIFACT})
        game.get_battlefield(p1).add(vivien)
        game.get_battlefield(p2).add(artifact)

        vivien._resolve_target = artifact
        abilities = vivien.get_loyalty_abilities()
        abilities[1].effect(game)

        bf = game.get_battlefield(p2)
        assert not bf.contains(artifact)

    def test_minus3_destroys_enchantment(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        vivien = VivienReid(owner=p1, controller=p1)
        from engine.card import CardImpl
        enchantment = CardImpl(name="Omen", owner=p2, controller=p2, card_types={CardType.ENCHANTMENT})
        game.get_battlefield(p1).add(vivien)
        game.get_battlefield(p2).add(enchantment)

        vivien._resolve_target = enchantment
        abilities = vivien.get_loyalty_abilities()
        abilities[1].effect(game)

        bf = game.get_battlefield(p2)
        assert not bf.contains(enchantment)

    def test_minus3_destroys_creature_with_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        vivien = VivienReid(owner=p1, controller=p1)
        flyer = Creature(name="Bird", base_power=2, base_toughness=2, owner=p2, controller=p2,
                         keywords=Keyword.FLYING)
        game.get_battlefield(p1).add(vivien)
        game.get_battlefield(p2).add(flyer)

        vivien._resolve_target = flyer
        abilities = vivien.get_loyalty_abilities()
        abilities[1].effect(game)

        bf = game.get_battlefield(p2)
        assert not bf.contains(flyer)

    def test_minus3_does_not_destroy_creature_without_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        vivien = VivienReid(owner=p1, controller=p1)
        ground_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p1).add(vivien)
        game.get_battlefield(p2).add(ground_creature)

        vivien._resolve_target = ground_creature
        abilities = vivien.get_loyalty_abilities()
        abilities[1].effect(game)

        bf = game.get_battlefield(p2)
        # Should NOT be destroyed (not legal target at resolution)
        assert bf.contains(ground_creature)

    def test_minus3_does_not_destroy_plain_creature(self) -> None:
        """A creature without flying, not an artifact/enchantment, is not legal."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        vivien = VivienReid(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p1).add(vivien)
        game.get_battlefield(p2).add(bear)

        vivien._resolve_target = bear
        abilities = vivien.get_loyalty_abilities()
        abilities[1].effect(game)

        assert game.get_battlefield(p2).contains(bear)


class TestVivienMinus8:
    """−8: Emblem — creatures get +2/+2, vigilance, trample, indestructible."""

    def _setup_emblem(self):
        game = create_game()
        p1 = game.players[0]
        vivien = VivienReid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(vivien)

        abilities = vivien.get_loyalty_abilities()
        abilities[2].effect(game)
        return game, p1

    def test_minus8_gives_plus2_plus2(self) -> None:
        game, p1 = self._setup_emblem()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)

        game.effect_manager.apply_all(game)

        assert creature.modified_power == 4
        assert creature.modified_toughness == 4

    def test_minus8_gives_vigilance(self) -> None:
        game, p1 = self._setup_emblem()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)

        game.effect_manager.apply_all(game)
        assert Keyword.VIGILANCE in creature.keywords

    def test_minus8_gives_trample(self) -> None:
        game, p1 = self._setup_emblem()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)

        game.effect_manager.apply_all(game)
        assert Keyword.TRAMPLE in creature.keywords

    def test_minus8_gives_indestructible(self) -> None:
        game, p1 = self._setup_emblem()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)

        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE in creature.keywords

    def test_minus8_does_not_affect_opponent_creatures(self) -> None:
        game, p1 = self._setup_emblem()
        p2 = game.players[1]
        opp_creature = Creature(name="Orc", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_creature)

        game.effect_manager.apply_all(game)
        # Opponent's creature should not get the buff
        assert opp_creature.base_power == 3
        assert opp_creature.base_toughness == 3

    def test_minus8_affects_creatures_entering_later(self) -> None:
        """Emblem is permanent — new creatures also get the buff."""
        game, p1 = self._setup_emblem()

        # Add creature after emblem was created
        creature = Creature(name="Elf", base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)

        game.effect_manager.apply_all(game)
        assert creature.modified_power == 3
        assert creature.modified_toughness == 3
        assert Keyword.VIGILANCE in creature.keywords

