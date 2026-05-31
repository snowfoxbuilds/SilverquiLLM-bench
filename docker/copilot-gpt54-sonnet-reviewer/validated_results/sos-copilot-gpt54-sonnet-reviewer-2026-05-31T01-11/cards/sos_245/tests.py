"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


def _creature(name: str, power: int = 1, toughness: int = 1) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)


def _cast_witherbloom(game, player_index: int, witherbloom: WitherbloomTheBalancer) -> None:
    player = game.players[player_index]
    engine_cast_spell(game, player, witherbloom)
    _resolve_all(game)


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_legendary_elder_dragon_creature_named_and_costed(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_has_flying_deathtouch_and_five_five_stats(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestWitherbloomTheBalancerAffinity:
    """Witherbloom should reduce costs based on creatures you control."""

    def test_self_affinity_counts_only_your_creatures_on_the_battlefield(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_first = _creature("Rot Farm Acolyte")
        your_second = _creature("Marshfield Adept")
        non_creature = CardImpl(name="Field Notes")
        opposing_creature = _creature("Opponent's Creature")

        set_board_state(game, 0, battlefield=[your_first, your_second, non_creature])
        set_board_state(game, 1, battlefield=[opposing_creature])

        assert card.cost_reduction(game) == 2

    def test_casts_for_two_less_with_two_creatures_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        first_helper = _creature("Campus Composter")
        second_helper = _creature("Bog Archivist")

        set_board_state(
            game,
            0,
            battlefield=[first_helper, second_helper],
            hand=[witherbloom],
            mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        engine_cast_spell(game, p1, witherbloom)
        _resolve_all(game)

        assert game.get_battlefield(p1).contains(witherbloom)


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries only."""

    def test_your_instant_spell_gets_affinity_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        helper = _creature("Student Naturalist")
        spell = Instant(
            name="Wither Lecture",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{B}"),
        )

        set_board_state(
            game,
            0,
            battlefield=[helper],
            hand=[witherbloom, spell],
            mana={ManaType.COLORLESS: 6, ManaType.BLACK: 2, ManaType.GREEN: 1},
        )

        _cast_witherbloom(game, 0, witherbloom)
        engine_cast_spell(game, p1, spell)
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(spell)

    def test_your_sorcery_spell_gets_affinity_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        first_helper = _creature("Herbal Apprentice")
        second_helper = _creature("Fen Pupil")
        spell = Sorcery(
            name="Balancing Thesis",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{G}"),
        )

        set_board_state(
            game,
            0,
            battlefield=[first_helper, second_helper],
            hand=[witherbloom, spell],
            mana={ManaType.COLORLESS: 6, ManaType.BLACK: 1, ManaType.GREEN: 2},
        )

        _cast_witherbloom(game, 0, witherbloom)
        engine_cast_spell(game, p1, spell)
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(spell)

    def test_granted_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Instant(
            name="Measured Decay",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{B}"),
        )
        opposing_first = _creature("Opposing Bear")
        opposing_second = _creature("Opposing Wolf")
        opposing_third = _creature("Opposing Spider")

        set_board_state(
            game,
            0,
            hand=[witherbloom, spell],
            mana={ManaType.COLORLESS: 6, ManaType.BLACK: 2, ManaType.GREEN: 1},
        )
        set_board_state(game, 1, battlefield=[opposing_first, opposing_second, opposing_third])

        _cast_witherbloom(game, 0, witherbloom)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, spell)

    def test_opponents_instants_and_sorceries_do_not_get_affinity(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        opponent_first = _creature("Opponent's Assistant")
        opponent_second = _creature("Opponent's Witness")
        opposing_spell = Instant(
            name="Stolen Formula",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{B}"),
        )

        set_board_state(
            game,
            0,
            hand=[witherbloom],
            mana={ManaType.COLORLESS: 6, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[opponent_first, opponent_second],
            hand=[opposing_spell],
            mana={ManaType.BLACK: 1},
        )

        _cast_witherbloom(game, 0, witherbloom)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p2, opposing_spell)

    def test_noninstant_and_nonsorcery_spells_you_cast_do_not_get_affinity(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        first_helper = _creature("Compost Intern")
        second_helper = _creature("Mire Trainee")
        creature_spell = Creature(
            name="Bog Scholar",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{G}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(
            game,
            0,
            battlefield=[first_helper, second_helper],
            hand=[witherbloom, creature_spell],
            mana={ManaType.COLORLESS: 6, ManaType.BLACK: 1, ManaType.GREEN: 2},
        )

        _cast_witherbloom(game, 0, witherbloom)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, creature_spell)
