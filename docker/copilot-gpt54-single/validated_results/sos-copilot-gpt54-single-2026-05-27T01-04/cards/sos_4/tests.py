"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _seed_library(player, count: int, *, prefix: str) -> None:
    """Add *count* simple sorceries to *player*'s library for draw tests."""
    for i in range(count):
        player.zones[Zone.LIBRARY].add(
            Sorcery(
                name=f"{prefix} {i}",
                owner=player,
                controller=player,
            )
        )


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_a_sorcery_named_together_as_one(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Together as One"
        assert CardType.SORCERY in card.card_types

    def test_has_six_generic_mana_cost_and_converge_rules_text(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")
        assert card.rules_text == (
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell."
        )


class TestTogetherAsOneTargeting:
    """The spell should ask for a player target and a separate any-target."""

    def test_get_targets_returns_target_player_then_any_target(self) -> None:
        game = create_game()
        requirements = TogetherAsOne(owner=None).get_targets(game)

        assert isinstance(requirements, list)
        assert len(requirements) == 2
        assert all(isinstance(req, TargetRequirement) for req in requirements)
        assert requirements[0].description == "target player"
        assert requirements[0].zone == Zone.BATTLEFIELD
        assert requirements[1].description == "any target"
        assert requirements[1].zone == Zone.BATTLEFIELD

    def test_target_player_requirement_accepts_players_and_rejects_creatures(self) -> None:
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        requirement = TogetherAsOne(owner=None).get_targets(game)[0]

        assert requirement.filter_fn(player) is True
        assert requirement.filter_fn(creature) is False

    def test_any_target_requirement_accepts_players_and_creatures_only(self) -> None:
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_target = Sorcery(name="Not a Target")
        requirement = TogetherAsOne(owner=None).get_targets(game)[1]

        assert requirement.filter_fn(player) is True
        assert requirement.filter_fn(creature) is True
        assert requirement.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge should scale all three effects from colors of mana spent."""

    def test_two_color_cast_draws_two_deals_two_to_creature_and_gains_two_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        creature = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        _seed_library(p2, 3, prefix="Opponent Draw")
        set_board_state(
            game,
            0,
            hand=[spell],
            life=10,
            mana={ManaType.WHITE: 4, ManaType.BLUE: 2},
        )
        set_board_state(game, 1, battlefield=[creature], life=20)

        cast_spell(game, 0, "Together as One", targets=[p2, creature])

        assert len(game.get_hand(p2)) == 2
        assert len(game.get_library(p2)) == 1
        assert creature.damage_marked == 2
        assert p1.life == 12
        assert p2.life == 20
        assert game.get_graveyard(p1).contains(spell)

    def test_any_target_can_be_a_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)

        _seed_library(p1, 3, prefix="Self Draw")
        set_board_state(
            game,
            0,
            hand=[spell],
            life=7,
            mana={
                ManaType.WHITE: 2,
                ManaType.BLUE: 2,
                ManaType.BLACK: 2,
            },
        )
        set_board_state(game, 1, life=20)

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(game.get_hand(p1)) == 3
        assert len(game.get_library(p1)) == 0
        assert p2.life == 17
        assert p1.life == 10
        assert game.get_graveyard(p1).contains(spell)

    def test_colorless_mana_makes_x_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)

        _seed_library(p2, 2, prefix="Zero Draw")
        set_board_state(
            game,
            0,
            hand=[spell],
            life=9,
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, life=14)

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2)) == 0
        assert len(game.get_library(p2)) == 2
        assert p2.life == 14
        assert p1.life == 9
        assert game.get_graveyard(p1).contains(spell)
