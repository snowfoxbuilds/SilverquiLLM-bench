"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, Color, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _seed_library(player, count: int) -> None:
    """Add *count* placeholder cards to *player*'s library."""
    for idx in range(count):
        card = Sorcery(name=f"Library Card {idx}")
        card.owner = player
        card.controller = player
        player.zones[Zone.LIBRARY].add(card)


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_name_mana_cost_and_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

    def test_rules_text_matches_spec(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.rules_text == (
            "Converge — Target player draws X cards, Together as One deals X "
            "damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell."
        )


class TestTogetherAsOneTargeting:
    """Target declarations should match the card's two-target contract."""

    def test_get_targets_returns_target_player_and_any_target(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].description == "target player"
        assert reqs[1].description == "any target"
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD

    def test_target_player_filter_accepts_only_players(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        player = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)

        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is False

    def test_any_target_filter_accepts_players_and_creatures_only(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        player = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        non_target = Sorcery(name="Divination")

        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Resolution should use X = distinct colors of mana spent to cast it."""

    def test_on_resolve_draws_deals_damage_to_player_and_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _seed_library(p2, 3)
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]
        spell.chosen_targets = [p2, p2]

        spell.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == 3
        assert p2.life == 17
        assert p1.life == 23

    def test_on_resolve_can_damage_a_creature_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(
            name="Grizzly Bears",
            owner=game.players[1],
            controller=game.players[1],
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(game.players[1]).add(bear)
        _seed_library(p1, 2)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE]
        spell.chosen_targets = [p1, bear]

        spell.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == 2
        assert bear.damage_marked == 2
        assert p1.life == 22


class TestTogetherAsOneCasting:
    """The cast pipeline should feed converge with distinct mana colors spent."""

    def test_cast_spell_uses_distinct_colors_spent_for_x(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(
            name="Target Bear",
            base_power=2,
            base_toughness=2,
        )
        _seed_library(p2, 2)
        set_board_state(
            game,
            0,
            hand=[TogetherAsOne(owner=p1, controller=p1)],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.COLORLESS: 4,
            },
        )
        set_board_state(game, 1, battlefield=[bear])

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(game.get_hand(p2).get_all()) == 2
        assert bear.damage_marked == 2
        assert p1.life == 22

    def test_cast_spell_with_only_colorless_mana_makes_x_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(
            game,
            0,
            hand=[TogetherAsOne(owner=p1, controller=p1)],
            mana={ManaType.COLORLESS: 6},
        )

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(game.get_hand(p1).get_all()) == 0
        assert p1.life == 20
        assert p2.life == 20
