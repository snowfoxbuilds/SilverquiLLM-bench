"""Tests for SOS 199 — Lluwen, Exchange Student // Pest Friend."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_199.card_impl import LluwenExchangeStudentPestFriend
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.card import ActivatedAbility, CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, Phase, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestLluwenExchangeStudentPestFriendProperties:
    """Static front-face data should match the SOS 199 spec."""

    def test_is_legendary_elf_druid_creature(self) -> None:
        card = LluwenExchangeStudentPestFriend(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = LluwenExchangeStudentPestFriend(owner=None)

        assert card.name == "Lluwen, Exchange Student"
        assert card.mana_cost == ManaCost.parse("{2}{B}{G}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestLluwenExchangeStudentPestFriendPrepared:
    """Lluwen should follow the prepared-state contract from the spec text."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_pest_friend_and_unprepares_the_card(self) -> None:
        game = create_game()
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p1 = game.players[0]
        card = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Pest Friend"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{B/G}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="Lluwen, Exchange Student.*not prepared"):
            card.cast_prepared_spell_copy(game)


class TestLluwenExchangeStudentPestFriendActivatedAbility:
    """Lluwen should re-prepare by exiling a creature card from your graveyard at sorcery speed."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = LluwenExchangeStudentPestFriend(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_exiles_a_creature_card_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        creature_card = Creature(
            name="Expired Roommate",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        filler = CardImpl(name="Noncreature Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[creature_card, filler])
        p1._script.append(creature_card)
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is True
        assert game.get_exile(p1).contains(creature_card)
        assert not game.get_graveyard(p1).contains(creature_card)
        assert game.get_graveyard(p1).contains(filler)

    def test_activation_cost_fails_without_a_creature_card_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        filler = CardImpl(name="Only Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[filler])
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False
        assert game.get_graveyard(p1).contains(filler)
        assert game.get_exile(p1).get_all() == []

    def test_activation_cost_fails_outside_sorcery_speed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        creature_card = Creature(
            name="Expired Roommate",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[creature_card])
        p1._script.append(creature_card)
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False
        assert game.get_graveyard(p1).contains(creature_card)
        assert not game.get_exile(p1).contains(creature_card)

    def test_effect_makes_lluwen_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LluwenExchangeStudentPestFriend(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_unprepared()
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        assert card.is_prepared is True

