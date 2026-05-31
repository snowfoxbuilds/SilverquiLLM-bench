"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Artifact, Creature, Sorcery
from engine.types import Color, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _load_library(player, count: int) -> None:
    """Add *count* filler cards to the player's library."""
    for idx in range(count):
        player.zones[Zone.LIBRARY].add(
            Sorcery(
                name=f"Library Card {idx + 1}",
                owner=player,
                controller=player,
            )
        )


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery_named_and_costed(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """Together as One should declare a player target and an any-target target."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=game.players[0], controller=game.players[0]).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].description == "target player"
        assert reqs[1].description == "any target"

    def test_first_target_requirement_accepts_only_players(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = TogetherAsOne(owner=p1, controller=p1).get_targets(game)[0]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)

        assert req.filter_fn(p2) is True
        assert req.filter_fn(creature) is False

    def test_second_target_requirement_accepts_players_and_creatures_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = TogetherAsOne(owner=p1, controller=p1).get_targets(game)[1]
        creature = Creature(name="Hill Giant", base_power=3, base_toughness=3)
        artifact = Artifact(name="Mana Rock")

        assert req.filter_fn(p2) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(artifact) is False


class TestTogetherAsOneResolution:
    """Converge should scale all three effects from the colors of mana spent."""

    def test_colorless_only_payment_makes_x_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        target_creature = Creature(
            name="Wall of Mist",
            owner=p2,
            controller=p2,
            base_power=0,
            base_toughness=5,
        )

        _load_library(p2, 2)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, battlefield=[target_creature])

        cast_spell(game, 0, "Together as One", targets=[p2, target_creature])

        assert len(p2.zones[Zone.HAND].get_all()) == 0
        assert p1.life == 20
        assert p2.life == 20
        assert target_creature.damage_marked == 0

    def test_three_colors_draws_three_damages_creature_for_three_and_gains_three(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        target_creature = Creature(
            name="Colossodon",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=5,
        )

        _load_library(p2, 3)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 2,
                ManaType.BLUE: 2,
                ManaType.BLACK: 2,
            },
        )
        set_board_state(game, 1, battlefield=[target_creature])

        cast_spell(game, 0, "Together as One", targets=[p2, target_creature])

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert target_creature.damage_marked == 3
        assert p1.life == 23
        assert p2.life == 20

    def test_five_colors_can_damage_a_player_for_five(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)

        _load_library(p2, 5)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 2,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.RED: 1,
                ManaType.GREEN: 1,
            },
        )

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND].get_all()) == 5
        assert p1.life == 25
        assert p2.life == 15

    def test_illegal_damage_target_does_not_stop_draw_and_life_gain(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        target_creature = Creature(
            name="Runeclaw Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        _load_library(p2, 3)
        set_board_state(game, 1, battlefield=[target_creature])
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]
        spell.chosen_targets = [p2, target_creature]

        game.get_battlefield(p2).remove(target_creature)
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert p1.life == 23
        assert target_creature.damage_marked == 0
        assert p2.life == 20
