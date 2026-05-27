"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _load_library(player, count: int) -> None:
    """Put *count* placeholder cards into *player*'s library."""
    for idx in range(count):
        card = Sorcery(name=f"Library Card {idx + 1}")
        card.owner = player
        card.controller = player
        player.zones[Zone.LIBRARY].add(card)


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery_with_expected_cost_and_rules_text(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Together as One"
        assert CardType.SORCERY in card.card_types
        assert card.mana_cost == ManaCost.parse("{6}")
        assert card.rules_text == (
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell."
        )


class TestTogetherAsOneTargeting:
    """Target requirements should match 'target player' and 'any target'."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert all(isinstance(req, TargetRequirement) for req in reqs)

    def test_first_target_requirement_accepts_players_only(self) -> None:
        game = create_game()
        player_req = TogetherAsOne(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)

        assert player_req.zone == Zone.BATTLEFIELD
        assert player_req.filter_fn(game.players[0]) is True
        assert player_req.filter_fn(game.players[1]) is True
        assert player_req.filter_fn(creature) is False

    def test_second_target_requirement_accepts_player_or_creature(self) -> None:
        game = create_game()
        any_target_req = TogetherAsOne(owner=None).get_targets(game)[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        non_target = Sorcery(name="Not a legal target")

        assert any_target_req.zone == Zone.BATTLEFIELD
        assert any_target_req.filter_fn(game.players[0]) is True
        assert any_target_req.filter_fn(creature) is True
        assert any_target_req.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge should scale draw, damage, and life gain by colors spent."""

    def test_one_color_spent_draws_one_deals_one_to_creature_and_gains_one(self) -> None:
        game = create_game(player1_life=10)
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = Creature(
            name="Runeclaw Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 6})
        set_board_state(game, 1, battlefield=[bear])
        _load_library(p2, 1)

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(p2.zones[Zone.HAND]) == 1
        assert len(p2.zones[Zone.LIBRARY]) == 0
        assert bear.damage_marked == 1
        assert p1.life == 11
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_five_colors_spent_uses_distinct_color_count_for_all_effects(self) -> None:
        game = create_game(player1_life=7, player2_life=20)
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.RED: 2,
                ManaType.GREEN: 1,
            },
        )
        _load_library(p1, 5)

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(p1.zones[Zone.HAND]) == 5
        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert p2.life == 15
        assert p1.life == 12
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_colorless_mana_only_makes_x_zero(self) -> None:
        game = create_game(player1_life=13, player2_life=19)
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == 0
        assert p2.drawn_from_empty_library is False
        assert p2.life == 19
        assert p1.life == 13
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
