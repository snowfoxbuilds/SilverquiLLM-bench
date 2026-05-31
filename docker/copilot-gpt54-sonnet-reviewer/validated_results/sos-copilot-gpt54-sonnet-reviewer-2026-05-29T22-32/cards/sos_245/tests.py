"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Artifact, Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as cast_spell_to_stack, get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import cast_spell, create_game, set_board_state


def _set_main_phase(game) -> None:
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0


def _make_creature(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _make_instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _make_sorcery(name: str, cost: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


class TestWitherbloomTheBalancerProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords


class TestWitherbloomTheBalancerSelfAffinity:
    """The creature spell itself has affinity for creatures."""

    def test_self_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        ally_one = _make_creature("Ally One")
        ally_two = _make_creature("Ally Two")
        relic = Artifact(name="Campus Relic", mana_cost=ManaCost.parse("{2}"))
        enemy_one = _make_creature("Enemy One")
        enemy_two = _make_creature("Enemy Two")

        set_board_state(game, 0, battlefield=[ally_one, ally_two, relic], hand=[card])
        set_board_state(game, 1, battlefield=[enemy_one, enemy_two])

        assert get_cost_reduction(game, card, p1) == 2

    def test_self_affinity_can_reduce_generic_cost_to_black_green_only(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_creature(f"Creature {n}") for n in range(7)]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(card)

    def test_self_affinity_does_not_reduce_colored_mana_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_creature(f"Creature {n}") for n in range(8)]

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={ManaType.BLACK: 1},
        )

        with pytest.raises(CastingError):
            cast_spell_to_stack(game, p1, card)


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom grants affinity for creatures to your instants and sorceries."""

    def test_grants_affinity_to_your_instant_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _make_instant("Balancing Lesson", "{3}{U}")

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _make_creature("Ally One"), _make_creature("Ally Two")],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack) == 1
        assert p1.mana_pool.get(ManaType.BLUE) == 0

    def test_grants_affinity_to_your_sorcery_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _make_sorcery("Campus Ritual", "{4}{G}")

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[
                witherbloom,
                _make_creature("Ally One"),
                _make_creature("Ally Two"),
                _make_creature("Ally Three"),
            ],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack) == 1
        assert p1.mana_pool.get(ManaType.GREEN) == 0

    def test_granted_affinity_counts_only_your_creatures_not_opponents(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _make_instant("Selective Insight", "{4}{U}")

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _make_creature("Ally One")],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[
                _make_creature("Enemy One"),
                _make_creature("Enemy Two"),
                _make_creature("Enemy Three"),
            ],
        )

        p1.mana_pool.add(ManaType.COLORLESS, 2)

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack) == 1
        assert p1.mana_pool.total() == 0

    def test_granted_affinity_applies_to_your_instants_but_not_your_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant_spell = _make_instant("Aided Lesson", "{4}{G}")
        creature_spell = Creature(
            name="Unassisted Giant",
            mana_cost=ManaCost.parse("{4}{G}"),
            base_power=4,
            base_toughness=4,
        )

        set_board_state(
            game,
            0,
            battlefield=[
                witherbloom,
                _make_creature("Ally One"),
                _make_creature("Ally Two"),
                _make_creature("Ally Three"),
                _make_creature("Ally Four"),
            ],
            hand=[instant_spell],
            mana={ManaType.GREEN: 1},
        )

        cast_spell_to_stack(game, p1, instant_spell)
        assert len(game.stack) == 1

        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[
                witherbloom,
                _make_creature("Ally One"),
                _make_creature("Ally Two"),
                _make_creature("Ally Three"),
                _make_creature("Ally Four"),
            ],
            hand=[creature_spell],
            mana={ManaType.GREEN: 1},
        )

        with pytest.raises(CastingError):
            cast_spell_to_stack(game, p1, creature_spell)

    def test_granted_affinity_applies_to_your_spells_but_not_opponents_spells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_spell = _make_instant("Your Lecture", "{4}{U}")
        opponent_spell = _make_instant("Opponent Lecture", "{4}{U}")

        set_board_state(
            game,
            0,
            battlefield=[
                witherbloom,
                _make_creature("Ally One"),
                _make_creature("Ally Two"),
                _make_creature("Ally Three"),
                _make_creature("Ally Four"),
            ],
            hand=[your_spell],
            mana={ManaType.BLUE: 1},
        )

        cast_spell_to_stack(game, p1, your_spell)
        assert len(game.stack) == 1

        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[
                witherbloom,
                _make_creature("Ally One"),
                _make_creature("Ally Two"),
                _make_creature("Ally Three"),
                _make_creature("Ally Four"),
            ],
        )
        set_board_state(
            game,
            1,
            hand=[opponent_spell],
            mana={ManaType.BLUE: 1},
        )

        with pytest.raises(CastingError):
            cast_spell_to_stack(game, p2, opponent_spell)
