"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell, get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import create_game, set_board_state

ORACLE_TEXT = (
    "Affinity for creatures (This spell costs {1} less to cast for each creature "
    "you control.)\n"
    "Flying, deathtouch\n"
    "Instant and sorcery spells you cast have affinity for creatures."
)


def _creature(name: str) -> Creature:
    return Creature(name=name, base_power=1, base_toughness=1)


def _set_main_phase(game, player_index: int) -> None:
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_legendary_elder_dragon_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name_mana_cost_rules_text_and_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.rules_text == ORACLE_TEXT
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_deathtouch(self) -> None:
        keywords = WitherbloomTheBalancer(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.DEATHTOUCH in keywords


class TestWitherbloomTheBalancerAffinity:
    """Witherbloom itself has affinity for creatures."""

    def test_self_affinity_counts_only_your_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[_creature("Student 1"), _creature("Student 2"), _creature("Student 3")],
            hand=[card],
        )
        set_board_state(game, 1, battlefield=[_creature("Opponent 1"), _creature("Opponent 2")])

        assert get_cost_reduction(game, card, p1) == 3

    def test_self_affinity_is_clamped_to_six_generic_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[_creature(f"Token {index}") for index in range(7)],
            hand=[card],
        )

        assert get_cost_reduction(game, card, p1) == 6

    def test_casting_self_with_six_creatures_succeeds_with_only_black_and_green_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[_creature(f"Creature {index}") for index in range(6)],
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        _set_main_phase(game, 0)

        engine_cast_spell(game, p1, card)

        assert not game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.BLACK) == 0
        assert p1.mana_pool.get(ManaType.GREEN) == 0

    def test_casting_self_with_six_creatures_still_requires_black_and_green_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[_creature(f"Creature {index}") for index in range(6)],
            hand=[card],
            mana={ManaType.COLORLESS: 6},
        )
        _set_main_phase(game, 0)

        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, card)


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom grants creature-count cost reduction to your instants and sorceries."""

    def test_witherbloom_grants_affinity_to_your_instants(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant = Instant(name="Campus Insight", mana_cost=ManaCost.parse("{1}{U}"), owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[witherbloom],
            hand=[instant],
            mana={ManaType.BLUE: 1},
        )
        _set_main_phase(game, 0)

        engine_cast_spell(game, p1, instant)

        assert not game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.BLUE) == 0

    def test_witherbloom_grants_affinity_to_your_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        assistant = _creature("Assistant")
        sorcery = Sorcery(name="Field Lecture", mana_cost=ManaCost.parse("{2}{G}"), owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, assistant],
            hand=[sorcery],
            mana={ManaType.GREEN: 1},
        )
        _set_main_phase(game, 0)

        engine_cast_spell(game, p1, sorcery)

        assert not game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.GREEN) == 0

    def test_creature_spells_do_not_gain_affinity_from_witherbloom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        assistant = _creature("Assistant")
        creature_spell = Creature(
            name="Graduate Researcher",
            mana_cost=ManaCost.parse("{2}{G}"),
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, assistant],
            hand=[creature_spell],
            mana={ManaType.GREEN: 1},
        )
        _set_main_phase(game, 0)

        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, creature_spell)

    def test_opponents_instants_do_not_gain_affinity_from_your_witherbloom(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant = Instant(name="Foreign Insight", mana_cost=ManaCost.parse("{3}{U}"), owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Student 1"), _creature("Student 2")],
        )
        set_board_state(
            game,
            1,
            hand=[instant],
            mana={ManaType.BLUE: 1},
        )
        _set_main_phase(game, 1)

        with pytest.raises(CastingError):
            engine_cast_spell(game, p2, instant)
