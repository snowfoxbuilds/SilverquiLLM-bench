"""Tests for SOS 54 — Hydro-Channeler."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_54.card_impl import HydroChanneler
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid
from benchmarks.sos.workspace.engine.card import Creature, ManaAbility, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestHydroChannelerProperties:
    """Static card data should match the SOS 54 spec."""

    def test_is_merfolk_wizard_creature(self) -> None:
        card = HydroChanneler(owner=None)
        assert isinstance(card, Creature)
        assert "Merfolk" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = HydroChanneler(owner=None)
        assert card.name == "Hydro-Channeler"
        assert card.mana_cost == ManaCost.parse("{1}{U}")
        assert card.base_power == 1
        assert card.base_toughness == 3


class TestHydroChannelerManaAbilities:
    """Hydro-Channeler should provide two instant/sorcery-only mana abilities."""

    def test_has_two_mana_abilities(self) -> None:
        abilities = HydroChanneler(owner=None).get_mana_abilities()
        assert len(abilities) == 2
        assert all(isinstance(ability, ManaAbility) for ability in abilities)

    def test_first_mana_ability_taps_to_add_blue_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HydroChanneler(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True

        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_second_mana_ability_costs_one_and_tap_and_adds_the_chosen_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HydroChanneler(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1._script.append(ManaType.GREEN)
        ability = card.get_mana_abilities()[1]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert p1.mana_pool.total() == 0

        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.GREEN) == 1
        assert p1.mana_pool.total() == 1

    def test_second_mana_ability_fails_without_generic_mana_to_pay_for_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HydroChanneler(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[1]

        assert ability.cost(game, card) is False
        assert card.is_tapped is False
        assert p1.mana_pool.total() == 0

    def test_first_mana_ability_mana_cannot_be_spent_on_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HydroChanneler(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Lecture Hall Cub",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card], hand=[creature_spell])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.BLUE) == 1

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, creature_spell)

        assert game.get_hand(p1).contains(creature_spell)
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_second_mana_ability_mana_can_be_spent_on_a_sorcery_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = HydroChanneler(owner=p1, controller=p1)
        sorcery_spell = Sorcery(
            name="Lesson in Growth",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{G}"),
        )
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[sorcery_spell],
            mana={ManaType.COLORLESS: 1},
        )
        p1._script.append(ManaType.GREEN)
        ability = card.get_mana_abilities()[1]

        assert ability.cost(game, card) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.GREEN) == 1

        cast_spell_paid(game, p1, sorcery_spell)

        assert game.stack.peek().source is sorcery_spell
        assert p1.mana_pool.total() == 0
