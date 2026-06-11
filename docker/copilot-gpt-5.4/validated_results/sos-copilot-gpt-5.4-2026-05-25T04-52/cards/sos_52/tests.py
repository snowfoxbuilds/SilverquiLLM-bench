"""Tests for SOS 52 — Harmonized Trio // Brainstorm."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_52.card_impl import HarmonizedTrioBrainstorm
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Instant
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestHarmonizedTrioBrainstormProperties:
    """Static front-face data should match the SOS 52 spec."""

    def test_is_merfolk_bard_wizard_creature(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert isinstance(card, Creature)
        assert "Merfolk" in card.subtypes
        assert "Bard" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert card.name == "Harmonized Trio"
        assert card.mana_cost == ManaCost.parse("{U}")
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestHarmonizedTrioBrainstormPreparedAbility:
    """Harmonized Trio should prepare itself by tapping itself and two allies."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = HarmonizedTrioBrainstorm(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_taps_this_and_two_other_untapped_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = HarmonizedTrioBrainstorm(owner=p1, controller=p1)
        ally_one = Creature(name="Student One", owner=p1, controller=p1, base_power=1, base_toughness=1)
        ally_two = Creature(name="Student Two", owner=p1, controller=p1, base_power=1, base_toughness=1)
        opposing_creature = Creature(
            name="Opposing Student",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[card, ally_one, ally_two])
        game.get_battlefield(p2).add(opposing_creature)
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert ally_one.is_tapped is True
        assert ally_two.is_tapped is True
        assert opposing_creature.is_tapped is False
        assert card.is_prepared is False

    def test_activation_cost_fails_without_two_other_untapped_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = HarmonizedTrioBrainstorm(owner=p1, controller=p1)
        ally = Creature(name="Student One", owner=p1, controller=p1, base_power=1, base_toughness=1)
        tapped_ally = Creature(name="Busy Student", owner=p1, controller=p1, base_power=1, base_toughness=1)
        tapped_ally.is_tapped = True
        opposing_creature = Creature(
            name="Opposing Student",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[card, ally, tapped_ally])
        game.get_battlefield(p2).add(opposing_creature)
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False
        assert card.is_tapped is False
        assert ally.is_tapped is False
        assert tapped_ally.is_tapped is True
        assert opposing_creature.is_tapped is False

    def test_activated_ability_effect_makes_the_card_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HarmonizedTrioBrainstorm(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_brainstorm_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HarmonizedTrioBrainstorm(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Brainstorm"
        assert isinstance(stack_obj.source, Instant)
        assert stack_obj.source.mana_cost == ManaCost.parse("{U}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HarmonizedTrioBrainstorm(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
