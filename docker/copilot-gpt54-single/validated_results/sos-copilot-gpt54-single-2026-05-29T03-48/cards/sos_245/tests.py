"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import (
    CastingError,
    cast_spell as cast_spell_to_stack,
    get_cost_reduction,
)
from engine.types import Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import cast_spell, create_game, set_board_state


def _set_precombat_main(game, active_player_index: int = 0) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _creature(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _sorcery(name: str, cost: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_legendary_elder_dragon_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_and_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_deathtouch(self) -> None:
        keywords = WitherbloomTheBalancer(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.DEATHTOUCH in keywords


class TestWitherbloomTheBalancerSelfAffinity:
    """Witherbloom itself should have affinity for creatures while being cast."""

    def test_cost_reduction_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[_creature("P1 Bear"), _creature("P1 Wolf")])
        set_board_state(game, 1, battlefield=[_creature("P2 Bear"), _creature("P2 Wolf")])

        assert card.cost_reduction(game) == 2

    def test_self_affinity_allows_casting_with_only_colored_mana_when_you_control_six_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[_creature(f"Creature {idx}") for idx in range(6)],
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(card)

    def test_self_affinity_does_not_reduce_colored_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        _set_precombat_main(game)

        set_board_state(
            game,
            0,
            battlefield=[_creature(f"Creature {idx}") for idx in range(8)],
            hand=[card],
            mana={ManaType.BLACK: 1},
        )

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_to_stack(game, p1, card)


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries."""

    def test_your_instant_spell_gets_affinity_for_creatures_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _instant("Witherbloom Lesson", "{3}{B}")

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Pest"), _creature("Scholar")],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack.objects()) == 1
        assert game.stack.peek().source is spell

    def test_your_sorcery_spell_gets_affinity_for_creatures_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _sorcery("Campus Harvest", "{3}{G}")

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Pest"), _creature("Scholar")],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack.objects()) == 1
        assert game.stack.peek().source is spell

    def test_granted_affinity_reduction_counts_only_your_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _instant("Selective Reagent", "{4}{B}")

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("P1 Assistant")],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        set_board_state(game, 1, battlefield=[_creature("P2 One"), _creature("P2 Two")])
        assert get_cost_reduction(game, spell, p1) == 2

    def test_granted_affinity_applies_to_instants_but_not_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant_spell = _instant("Practical Formula", "{4}{G}")
        creature_spell = Creature(
            name="Study Hulk",
            mana_cost=ManaCost.parse("{4}{G}"),
            base_power=4,
            base_toughness=4,
            owner=p1,
            controller=p1,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Pest"), _creature("Scholar"), _creature("Apprentice")],
            hand=[instant_spell, creature_spell],
        )
        assert get_cost_reduction(game, instant_spell, p1) == 4
        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_granted_affinity_applies_only_to_your_spells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_spell = _instant("Resident Formula", "{3}{B}")
        opposing_spell = _instant("Borrowed Formula", "{3}{B}")

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Pest"), _creature("Scholar")],
            hand=[your_spell],
        )
        set_board_state(
            game,
            1,
            battlefield=[_creature("Opposing Pest"), _creature("Opposing Scholar"), _creature("Opposing Assistant")],
            hand=[opposing_spell],
        )
        assert get_cost_reduction(game, your_spell, p1) == 3
        assert get_cost_reduction(game, opposing_spell, p2) == 0

    def test_multiple_instances_of_granted_affinity_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        first = WitherbloomTheBalancer(owner=p1, controller=p1)
        second = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _sorcery("Overgrown Thesis", "{5}{G}")

        set_board_state(
            game,
            0,
            battlefield=[first, second, _creature("Assistant")],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack.objects()) == 1
        assert game.stack.peek().source is spell
