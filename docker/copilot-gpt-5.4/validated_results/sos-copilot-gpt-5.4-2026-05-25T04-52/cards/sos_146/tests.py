"""Tests for SOS 146 — Emil, Vastlands Roamer."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_146.card_impl import EmilVastlandsRoamer
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Land
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, ManaType, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEmilVastlandsRoamerProperties:
    """Static card data should match the SOS 146 spec."""

    def test_is_legendary_elf_druid_creature(self) -> None:
        card = EmilVastlandsRoamer(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = EmilVastlandsRoamer(owner=None)

        assert card.name == "Emil, Vastlands Roamer"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmilVastlandsRoamerStaticAbility:
    """Emil should grant trample only to your countered creatures."""

    def test_only_your_creatures_with_plus_one_plus_one_counters_have_trample(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmilVastlandsRoamer(owner=p1, controller=p1)
        countered_ally = Creature(
            name="Countered Ally",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        plain_ally = Creature(
            name="Plain Ally",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        countered_enemy = Creature(
            name="Countered Enemy",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, countered_ally, plain_ally])
        set_board_state(game, 1, battlefield=[countered_enemy])
        add_counter(game, countered_ally, "+1/+1")
        add_counter(game, countered_enemy, "+1/+1")

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert Keyword.TRAMPLE in countered_ally.keywords
        assert Keyword.TRAMPLE not in plain_ally.keywords
        assert Keyword.TRAMPLE not in countered_enemy.keywords


class TestEmilVastlandsRoamerActivatedAbility:
    """Emil should tap for a land-counted Fractal token."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = EmilVastlandsRoamer(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_five_mana_and_taps_emil(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmilVastlandsRoamer(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 4},
        )
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert p1.mana_pool.total() == 0

    def test_effect_creates_a_green_and_blue_fractal_with_counters_equal_to_differently_named_lands_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmilVastlandsRoamer(owner=p1, controller=p1)
        forest_a = Land(name="Forest", owner=p1, controller=p1)
        forest_b = Land(name="Forest", owner=p1, controller=p1)
        island = Land(name="Island", owner=p1, controller=p1)
        swamp = Land(name="Swamp", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[card, forest_a, forest_b, island])
        set_board_state(game, 1, battlefield=[swamp])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert "Fractal" in token.subtypes
        assert get_colors(token) == {Color.GREEN, Color.BLUE}
        assert token.plus_one_counters == 2
        assert token.power == 2
        assert token.toughness == 2
