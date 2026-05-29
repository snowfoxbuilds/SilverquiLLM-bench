"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell, get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import cast_spell, create_game, set_board_state


class LectureNotesInstant(Instant):
    """Simple instant used to validate granted affinity."""

    def __init__(self) -> None:
        super().__init__(
            name="Lecture Notes",
            mana_cost=ManaCost.parse("{6}{B}"),
        )


class FieldResearch(Sorcery):
    """Simple sorcery used to validate granted affinity."""

    def __init__(self) -> None:
        super().__init__(
            name="Field Research",
            mana_cost=ManaCost.parse("{6}{G}"),
        )


def _make_creatures(count: int) -> list[Creature]:
    return [
        Creature(
            name=f"Creature {index}",
            base_power=2,
            base_toughness=2,
        )
        for index in range(count)
    ]


def _set_sorcery_speed(game, player_index: int) -> None:
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = player_index
    game.priority_player_index = player_index


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_legendary_elder_dragon_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_and_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_deathtouch(self) -> None:
        keywords = WitherbloomTheBalancer(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.DEATHTOUCH in keywords


class TestWitherbloomTheBalancerSelfAffinity:
    """Witherbloom itself has affinity for creatures."""

    def test_self_affinity_counts_only_your_battlefield_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        hand_creature = Creature(name="Hand Creature", base_power=2, base_toughness=2)
        graveyard_creature = Creature(
            name="Graveyard Creature",
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=_make_creatures(2),
            hand=[card, hand_creature],
            graveyard=[graveyard_creature],
        )
        set_board_state(game, 1, battlefield=_make_creatures(3))

        assert get_cost_reduction(game, card, p1) == 2

    def test_self_affinity_can_reduce_generic_cost_to_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=_make_creatures(6),
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(card)
        assert p1.mana_pool.total() == 0

    def test_self_affinity_does_not_reduce_colored_mana_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=_make_creatures(6),
            hand=[card],
            mana={ManaType.BLACK: 1},
        )
        _set_sorcery_speed(game, 0)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, card)

        assert game.get_hand(p1).contains(card)
        assert not game.get_battlefield(p1).contains(card)


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom grants affinity for creatures to your instants and sorceries."""

    def test_granted_affinity_lets_you_cast_an_instant_for_only_its_colored_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = LectureNotesInstant()

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, *_make_creatures(5)],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 1
        assert not game.get_hand(p1).contains(spell)
        assert p1.mana_pool.total() == 0

    def test_granted_affinity_counts_witherbloom_and_other_creatures_for_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = FieldResearch()

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, *_make_creatures(2)],
            hand=[spell],
        )

        assert get_cost_reduction(game, spell, p1) == 3

    def test_granted_affinity_counts_only_your_creatures_not_opponents(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = LectureNotesInstant()

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, *_make_creatures(1)],
            hand=[spell],
        )
        set_board_state(game, 1, battlefield=_make_creatures(3))

        assert get_cost_reduction(game, spell, p1) == 2

    def test_granted_affinity_does_not_apply_to_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Campus Scavenger",
            mana_cost=ManaCost.parse("{6}{G}"),
            base_power=4,
            base_toughness=4,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, *_make_creatures(3)],
            hand=[creature_spell],
        )

        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_granted_affinity_does_not_apply_to_opponents_spells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        opponent_spell = LectureNotesInstant()

        set_board_state(game, 0, battlefield=[witherbloom, *_make_creatures(3)])
        set_board_state(game, 1, hand=[opponent_spell])

        assert get_cost_reduction(game, opponent_spell, p2) == 0

    def test_granted_affinity_requires_witherbloom_to_be_on_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = LectureNotesInstant()

        set_board_state(
            game,
            0,
            battlefield=_make_creatures(3),
            hand=[witherbloom, spell],
        )

        assert get_cost_reduction(game, spell, p1) == 0
