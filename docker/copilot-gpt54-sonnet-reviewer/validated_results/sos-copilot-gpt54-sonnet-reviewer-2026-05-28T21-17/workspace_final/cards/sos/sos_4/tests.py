"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant, Planeswalker, Sorcery
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestTogetherAsOneProperties:
    """Static card data should match the card spec."""

    def test_is_a_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """Together as One should declare its player target and damage target."""

    def test_get_targets_returns_target_player_and_any_target(self) -> None:
        game = create_game()

        requirements = TogetherAsOne(owner=None).get_targets(game)

        assert isinstance(requirements, list)
        assert len(requirements) == 2
        assert all(isinstance(req, TargetRequirement) for req in requirements)
        assert requirements[0].description == "target player"
        assert requirements[1].description == "any target"
        assert requirements[0].zone == Zone.BATTLEFIELD
        assert requirements[1].zone == Zone.BATTLEFIELD

    def test_target_filters_accept_player_for_draw_and_player_creature_or_planeswalker_for_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        walker = Planeswalker(name="Test Walker", starting_loyalty=4)
        non_target = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"))

        draw_target_req, damage_target_req = TogetherAsOne(owner=None).get_targets(game)

        assert draw_target_req.filter_fn(p1) is True
        assert draw_target_req.filter_fn(bear) is False
        assert damage_target_req.filter_fn(p1) is True
        assert damage_target_req.filter_fn(bear) is True
        assert damage_target_req.filter_fn(walker) is True
        assert damage_target_req.filter_fn(non_target) is False


class TestTogetherAsOneConvergeResolution:
    """Resolution should use the number of mana colors spent as X."""

    @staticmethod
    def _seed_library(player, count: int) -> None:
        for idx in range(count):
            card = Instant(
                name=f"Draw Fodder {idx}",
                mana_cost=ManaCost.parse("{U}"),
                owner=player,
                controller=player,
            )
            player.zones[Zone.LIBRARY].add(card)

    def test_two_colors_targeting_yourself_draws_two_deals_two_and_gains_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)

        self._seed_library(p1, 2)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 3, ManaType.BLUE: 3},
        )

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(game.get_hand(p1).get_all()) == 2
        assert p2.life == 18
        assert p1.life == 22

    def test_three_colors_can_draw_for_an_opponent_and_damage_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        ogre = Creature(
            name="Hill Ogre",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=5,
        )

        self._seed_library(p2, 3)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        set_board_state(game, 1, battlefield=[ogre])

        cast_spell(game, 0, "Together as One", targets=[p2, ogre])

        assert len(game.get_hand(p2).get_all()) == 3
        assert ogre.damage_marked == 3
        assert p1.life == 23

    def test_explicit_generic_payment_choices_can_make_x_three_from_an_ambiguous_pool(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)

        self._seed_library(p1, 3)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 3, ManaType.BLUE: 3, ManaType.BLACK: 3},
        )

        cast_spell(
            game,
            0,
            "Together as One",
            targets=[p1, p2],
            payment_choices={
                ManaType.WHITE: 2,
                ManaType.BLUE: 2,
                ManaType.BLACK: 2,
            },
        )

        assert len(game.get_hand(p1).get_all()) == 3
        assert p2.life == 17
        assert p1.life == 23

    def test_three_color_payment_can_damage_a_planeswalker_and_put_it_into_the_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        walker = Planeswalker(
            name="Test Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=3,
        )

        self._seed_library(p1, 3)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        set_board_state(game, 1, battlefield=[walker])

        cast_spell(game, 0, "Together as One", targets=[p1, walker])

        assert len(game.get_hand(p1).get_all()) == 3
        assert p1.life == 23
        assert p2.life == 20
        assert game.get_battlefield(p2).contains(walker) is False
        assert p2.zones[Zone.GRAVEYARD].contains(walker) is True

    def test_colorless_only_payment_makes_x_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
        )

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2).get_all()) == 0
        assert p2.life == 20
        assert p1.life == 20
