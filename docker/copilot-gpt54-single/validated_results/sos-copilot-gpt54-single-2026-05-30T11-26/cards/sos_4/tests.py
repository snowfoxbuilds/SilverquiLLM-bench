"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _add_library_cards(player, count: int) -> None:
    for idx in range(count):
        card = Sorcery(name=f"Library Card {idx}")
        card.owner = player
        card.controller = player
        player.zones[Zone.LIBRARY].add(card)


def _target_creature(owner, controller=None) -> Creature:
    return Creature(
        name="Target Bear",
        owner=owner,
        controller=controller or owner,
        base_power=2,
        base_toughness=2,
    )


class TestTogetherAsOneProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert all(isinstance(req, TargetRequirement) for req in reqs)

    def test_first_target_requirement_accepts_only_players(self) -> None:
        game = create_game()
        p1, _ = game.players
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        req = TogetherAsOne(owner=None).get_targets(game)[0]

        assert req.filter_fn(p1) is True
        assert req.filter_fn(creature) is False

    def test_second_target_requirement_accepts_any_target(self) -> None:
        game = create_game()
        p1, _ = game.players
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        non_target = CardImpl(name="Not a legal target")
        req = TogetherAsOne(owner=None).get_targets(game)[1]

        assert req.filter_fn(p1) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_target) is False


class TestTogetherAsOneConvergeResolution:
    def test_three_colors_make_target_player_draw_three_damage_creature_and_gain_three_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = _target_creature(owner=p2, controller=p2)
        _add_library_cards(p2, 3)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.COLORLESS: 3,
            },
        )
        set_board_state(game, 1, battlefield=[bear])

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert bear.damage_marked == 3
        assert p1.life == 23

    def test_any_target_can_be_a_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _add_library_cards(p1, 2)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.COLORLESS: 4,
            },
        )

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(p1.zones[Zone.HAND].get_all()) == 2
        assert p2.life == 18
        assert p1.life == 22

    def test_colorless_mana_makes_x_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = _target_creature(owner=p2, controller=p2)
        _add_library_cards(p2, 2)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, battlefield=[bear])

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(p2.zones[Zone.HAND].get_all()) == 0
        assert bear.damage_marked == 0
        assert p1.life == 20
