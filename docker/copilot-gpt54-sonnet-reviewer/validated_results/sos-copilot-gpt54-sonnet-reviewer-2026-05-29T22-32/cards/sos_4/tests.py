"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Planeswalker, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, cast_spell, set_board_state


def _load_library(player, count: int) -> None:
    for i in range(count):
        card = Sorcery(name=f"Library Card {i}", mana_cost=ManaCost.parse("{1}"))
        card.owner = player
        card.controller = player
        player.zones[Zone.LIBRARY].add(card)


class TestTogetherAsOneProperties:
    """Static characteristics from the card spec."""

    def test_is_sorcery_named_and_costed(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """The spell needs two different targets: a player and any target."""

    def test_get_targets_returns_target_player_then_any_target(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert all(isinstance(req, TargetRequirement) for req in reqs)

        player_req, damage_req = reqs
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        planeswalker = Planeswalker(name="Walker", starting_loyalty=5)

        assert player_req.filter_fn(game.players[0]) is True
        assert player_req.filter_fn(creature) is False

        assert damage_req.filter_fn(game.players[0]) is True
        assert damage_req.filter_fn(creature) is True
        assert damage_req.filter_fn(planeswalker) is True


class TestTogetherAsOneConvergeResolution:
    """Resolution uses the number of distinct colors spent to cast the spell."""

    def test_colorless_only_payment_makes_x_zero(self) -> None:
        game = create_game(player1_life=11, player2_life=17)
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=None)
        blocker = Creature(
            name="Sturdy Bear",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )

        set_board_state(
            game,
            0,
            hand=[spell],
            life=11,
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, battlefield=[blocker], life=17)
        _load_library(p2, 3)

        cast_spell(game, 0, "Together as One", targets=[p2, blocker])

        assert len(game.get_hand(p2).get_all()) == 0
        assert blocker.damage_marked == 0
        assert p1.life == 11
        assert p2.life == 17

    def test_two_colors_make_target_player_draw_two_damage_creature_and_gain_two(self) -> None:
        game = create_game(player1_life=10, player2_life=20)
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=None)
        creature = Creature(
            name="Hill Giant",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )

        set_board_state(
            game,
            0,
            hand=[spell],
            life=10,
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.COLORLESS: 4},
        )
        set_board_state(game, 1, battlefield=[creature], life=20)
        _load_library(p2, 2)

        cast_spell(game, 0, "Together as One", targets=[p2, creature])

        assert len(game.get_hand(p2).get_all()) == 2
        assert creature.damage_marked == 2
        assert p1.life == 12
        assert p2.life == 20

    def test_repeated_same_color_counts_once_for_converge(self) -> None:
        game = create_game(player1_life=7, player2_life=20)
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=None)

        set_board_state(
            game,
            0,
            hand=[spell],
            life=7,
            mana={ManaType.GREEN: 3, ManaType.COLORLESS: 3},
        )
        set_board_state(game, 1, life=20)
        _load_library(p2, 1)

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2).get_all()) == 1
        assert p2.life == 19
        assert p1.life == 8

    def test_damage_target_can_be_a_planeswalker(self) -> None:
        game = create_game(player1_life=9, player2_life=20)
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=None)
        walker = Planeswalker(
            name="Test Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=7,
        )

        set_board_state(
            game,
            0,
            hand=[spell],
            life=9,
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.COLORLESS: 3,
            },
        )
        set_board_state(game, 1, battlefield=[walker], life=20)
        _load_library(p1, 3)

        cast_spell(game, 0, "Together as One", targets=[p1, walker])

        assert len(game.get_hand(p1).get_all()) == 3
        assert walker.loyalty == 4
        assert p1.life == 12
