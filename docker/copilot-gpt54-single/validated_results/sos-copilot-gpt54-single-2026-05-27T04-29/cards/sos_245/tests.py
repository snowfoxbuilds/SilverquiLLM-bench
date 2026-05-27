"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Artifact, Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as cast_without_resolution, get_cost_reduction
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import cast_spell, create_game, set_board_state


class SampleLecture(Instant):
    """Simple instant used to verify granted affinity during casting."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Sample Lecture")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        super().__init__(**kwargs)


class SampleResearch(Sorcery):
    """Simple sorcery used to verify granted affinity queries."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Sample Research")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        super().__init__(**kwargs)


def _set_main_phase(game, player_index: int) -> None:
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _creature(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestWitherbloomTheBalancerProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_elder_dragon_creature_with_specified_stats(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Witherbloom, the Balancer"
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_black_and_green(self) -> None:
        assert WitherbloomTheBalancer(owner=None).colors == {Color.BLACK, Color.GREEN}


class TestWitherbloomTheBalancerAffinity:
    """Affinity for creatures on itself and spells it grants the ability to."""

    def test_self_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        own_creature_a = _creature("Pest A")
        own_creature_b = _creature("Pest B")
        own_artifact = Artifact(name="Campus Relic")
        opposing_creature = _creature("Opponent Pest")

        set_board_state(game, 0, battlefield=[own_creature_a, own_creature_b, own_artifact])
        set_board_state(game, 1, battlefield=[opposing_creature])

        assert get_cost_reduction(game, witherbloom, p1) == 2

    def test_can_be_cast_for_three_black_green_when_you_control_three_other_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[_creature("Pest A"), _creature("Pest B"), _creature("Pest C")],
            hand=[witherbloom],
            mana={
                ManaType.COLORLESS: 3,
                ManaType.BLACK: 1,
                ManaType.GREEN: 1,
            },
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(witherbloom)

    def test_self_affinity_does_not_remove_its_colored_mana_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[
                _creature("Pest A"),
                _creature("Pest B"),
                _creature("Pest C"),
                _creature("Pest D"),
                _creature("Pest E"),
                _creature("Pest F"),
            ],
            hand=[witherbloom],
            mana={ManaType.BLACK: 1},
        )
        _set_main_phase(game, 0)

        assert get_cost_reduction(game, witherbloom, p1) == 6

        with pytest.raises(CastingError):
            cast_without_resolution(game, p1, witherbloom)

        assert game.get_hand(p1).contains(witherbloom)

    def test_your_instant_spell_can_be_cast_using_granted_affinity_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant_spell = SampleLecture(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Pest A"), _creature("Pest B")],
            hand=[instant_spell],
            mana={ManaType.BLUE: 1},
        )
        _set_main_phase(game, 0)

        cast_without_resolution(game, p1, instant_spell)

        assert game.stack.peek().source is instant_spell
        assert instant_spell.mana_spent_to_cast == 1

    def test_your_sorcery_spell_gets_affinity_based_on_your_creatures_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = SampleResearch(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Pest A"), Artifact(name="Campus Relic")],
        )
        set_board_state(game, 1, battlefield=[_creature("Opponent Pest A"), _creature("Opponent Pest B")])

        assert get_cost_reduction(game, spell, p1) == 2

    def test_your_creature_spells_do_not_gain_affinity_from_witherbloom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Unrelated Creature",
            mana_cost=ManaCost.parse("{2}{G}"),
            base_power=3,
            base_toughness=3,
            owner=p1,
            controller=p1,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Pest A"), _creature("Pest B")],
            hand=[creature_spell],
            mana={ManaType.GREEN: 1},
        )
        _set_main_phase(game, 0)

        with pytest.raises(CastingError):
            cast_without_resolution(game, p1, creature_spell)

    def test_opponents_instant_spells_do_not_gain_affinity_from_your_witherbloom(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        opposing_spell = SampleLecture(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[witherbloom])
        set_board_state(
            game,
            1,
            battlefield=[_creature("Opponent Pest A"), _creature("Opponent Pest B"), _creature("Opponent Pest C")],
            hand=[opposing_spell],
            mana={ManaType.BLUE: 1},
        )
        _set_main_phase(game, 1)

        with pytest.raises(CastingError):
            cast_without_resolution(game, p2, opposing_spell)
