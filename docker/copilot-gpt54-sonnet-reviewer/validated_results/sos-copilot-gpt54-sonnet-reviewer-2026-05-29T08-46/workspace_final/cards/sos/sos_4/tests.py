"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Planeswalker, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement
from test_utils import cast_spell, create_game, set_board_state


def _make_deck(prefix: str, count: int) -> list[Sorcery]:
    """Build a simple deck with enough cards to support draw tests."""
    return [
        Sorcery(name=f"{prefix} Card {idx}", mana_cost=ManaCost.parse("{1}"))
        for idx in range(count)
    ]


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

    def test_name_and_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """Together as One should require a player target and a damage target."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)

    def test_first_requirement_accepts_only_players(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}

        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(creature) is False

    def test_second_requirement_accepts_players_creatures_and_planeswalkers(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        planeswalker = Planeswalker(name="Test Walker", starting_loyalty=4)
        non_target = Sorcery(name="Not a legal damage target")

        assert req.filter_fn(game.players[1]) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(planeswalker) is True
        assert req.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge should set one shared X for all three parts of the spell."""

    def test_five_color_cast_makes_target_player_draw_five_deals_five_and_gains_five(self) -> None:
        game = create_game(deck1=_make_deck("P1", 20), deck2=_make_deck("P2", 20))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            life=20,
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.RED: 1,
                ManaType.GREEN: 1,
                ManaType.COLORLESS: 1,
            },
        )
        opponent_hand_before = len(game.get_hand(p2).get_all())

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2).get_all()) == opponent_hand_before + 5
        assert p2.life == 15
        assert p1.life == 25

    def test_single_color_cast_counts_only_distinct_color_for_x(self) -> None:
        game = create_game(deck1=_make_deck("P1", 20), deck2=_make_deck("P2", 20))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, hand=[spell], life=20, mana={ManaType.RED: 6})
        set_board_state(game, 1, battlefield=[bear], life=20)

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        assert len(game.get_hand(p1).get_all()) == 1
        assert bear.damage_marked == 1
        assert p1.life == 21

    def test_colorless_only_cast_uses_zero_for_draw_damage_and_life_gain(self) -> None:
        game = create_game(deck1=_make_deck("P1", 20), deck2=_make_deck("P2", 20))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[spell], life=20, mana={ManaType.COLORLESS: 6})
        opponent_hand_before = len(game.get_hand(p2).get_all())

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2).get_all()) == opponent_hand_before
        assert p2.life == 20
        assert p1.life == 20

    def test_five_color_cast_can_damage_planeswalker_target_and_put_it_into_graveyard(self) -> None:
        game = create_game(deck1=_make_deck("P1", 20), deck2=_make_deck("P2", 20))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        walker = Planeswalker(
            name="Test Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=5,
        )

        set_board_state(
            game,
            0,
            hand=[spell],
            life=20,
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.RED: 1,
                ManaType.GREEN: 1,
                ManaType.COLORLESS: 1,
            },
        )
        set_board_state(game, 1, battlefield=[walker], life=20)

        cast_spell(game, 0, "Together as One", targets=[p1, walker])

        assert walker.loyalty == 0
        assert not game.get_battlefield(p2).contains(walker)
        assert game.get_graveyard(p2).contains(walker)
        assert p1.life == 25
