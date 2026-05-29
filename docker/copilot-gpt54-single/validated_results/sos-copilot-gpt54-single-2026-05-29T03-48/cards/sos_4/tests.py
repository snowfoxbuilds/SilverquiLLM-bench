"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant, Sorcery
from engine.types import Color, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _add_cards_to_library(game, player, count: int) -> None:
    library = game.get_library(player)
    for idx in range(count):
        card = Instant(name=f"Library Card {idx + 1}")
        card.owner = player
        card.controller = player
        library.add(card)


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """Together as One targets one player and one any-target object."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)

    def test_first_target_requirement_is_target_player(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        player = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)

        assert req.zone == Zone.BATTLEFIELD
        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is False

    def test_second_target_requirement_accepts_any_target(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        player = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        non_target = Instant(name="Not a target")

        assert req.zone == Zone.BATTLEFIELD
        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge sets X from colors spent and applies all three effects."""

    def test_on_resolve_draws_cards_damages_creature_and_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[bear])
        _add_cards_to_library(game, p2, 2)

        spell.colors_spent = [Color.WHITE, Color.BLUE]
        spell.chosen_targets = [p2, bear]

        before_hand = len(game.get_hand(p2).get_all())
        before_life = p1.life
        before_damage = bear.damage_marked

        spell.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == before_hand + 2
        assert bear.damage_marked == before_damage + 2
        assert p1.life == before_life + 2

    def test_casting_with_only_colorless_mana_makes_x_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, battlefield=[bear])
        _add_cards_to_library(game, p2, 1)

        before_hand = len(game.get_hand(p2).get_all())
        before_life = p1.life
        before_damage = bear.damage_marked

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(game.get_hand(p2).get_all()) == before_hand
        assert bear.damage_marked == before_damage
        assert p1.life == before_life
        assert game.get_graveyard(p1).contains(spell)

    def test_cast_pipeline_uses_distinct_mana_colors_for_x(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
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
        _add_cards_to_library(game, p2, 3)

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2).get_all()) == 3
        assert p2.life == 17
        assert p1.life == 23
        assert game.get_graveyard(p1).contains(spell)
