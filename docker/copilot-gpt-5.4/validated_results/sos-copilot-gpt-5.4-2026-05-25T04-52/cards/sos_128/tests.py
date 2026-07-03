"""Tests for SOS 128 — Rubble Rouser."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_128.card_impl import RubbleRouser
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestRubbleRouserProperties:
    """Static card data should match the SOS 128 spec."""

    def test_is_dwarf_sorcerer_creature(self) -> None:
        card = RubbleRouser(owner=None)

        assert isinstance(card, Creature)
        assert "Dwarf" in card.subtypes
        assert "Sorcerer" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = RubbleRouser(owner=None)

        assert card.name == "Rubble Rouser"
        assert card.mana_cost == ManaCost.parse("{2}{R}")
        assert card.base_power == 1
        assert card.base_toughness == 4


class TestRubbleRouserEnters:
    """Rubble Rouser should optionally rummage when it resolves."""

    def test_on_resolve_may_discard_a_card_to_draw_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        keep = CardImpl(name="Keep", owner=p1, controller=p1)
        discard_card = CardImpl(name="Spent Sketch", owner=p1, controller=p1)
        drawn = CardImpl(name="Fresh Sketch", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[keep, discard_card])
        game.get_library(p1).add(drawn)
        p1._script.extend([True, discard_card])

        card = RubbleRouser(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).contains(keep)
        assert game.get_hand(p1).contains(drawn)
        assert not game.get_hand(p1).contains(discard_card)
        assert game.get_graveyard(p1).contains(discard_card)

    def test_on_resolve_can_decline_to_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kept = CardImpl(name="Kept Notes", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[kept])
        p1._script.append(False)

        card = RubbleRouser(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == [kept]
        assert game.get_graveyard(p1).get_all() == []

    def test_on_resolve_is_a_noop_when_you_have_no_card_to_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RubbleRouser(owner=p1, controller=p1)

        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []


class TestRubbleRouserManaAbility:
    """Rubble Rouser should convert graveyard cards into red mana and damage."""

    def test_has_a_single_mana_ability(self) -> None:
        abilities = RubbleRouser(owner=None).get_mana_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ManaAbility)

    def test_mana_ability_cost_taps_this_creature_and_exiles_a_graveyard_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RubbleRouser(owner=p1, controller=p1)
        fuel = CardImpl(name="Old Formula", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[fuel])
        p1._script.append(fuel)
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert not game.get_graveyard(p1).contains(fuel)
        assert game.get_exile(p1).contains(fuel)

    def test_mana_ability_fails_without_a_graveyard_card_to_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RubbleRouser(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is False
        assert card.is_tapped is False

    def test_mana_ability_adds_red_mana_and_deals_one_damage_to_each_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RubbleRouser(owner=p1, controller=p1)
        fuel = CardImpl(name="Spent Idea", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[fuel])
        p1._script.append(fuel)
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True

        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.RED) == 1
        assert p1.life == 20
        assert p2.life == 19
