"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _creature(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _set_main_phase(game, player_index: int = 0) -> None:
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_a_legendary_elder_dragon_creature_with_flying_and_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_name_mana_cost_and_power_toughness_match_the_spec(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestWitherbloomTheBalancerAffinity:
    """Witherbloom should apply affinity for creatures to itself and your spells."""

    def test_self_affinity_counts_only_your_creatures(self) -> None:
        game = create_game()
        player = game.players[0]
        card = WitherbloomTheBalancer(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[_creature("Pest A"), _creature("Pest B")],
            hand=[card],
            mana={ManaType.COLORLESS: 2, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[
                _creature("Enemy A"),
                _creature("Enemy B"),
                _creature("Enemy C"),
                _creature("Enemy D"),
            ],
        )
        _set_main_phase(game)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, player, card)

        assert player.zones[Zone.HAND].contains(card)
        assert not player.zones[Zone.BATTLEFIELD].contains(card)

    def test_self_affinity_can_reduce_all_generic_mana(self) -> None:
        game = create_game()
        player = game.players[0]
        card = WitherbloomTheBalancer(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[
                _creature("Creature 1"),
                _creature("Creature 2"),
                _creature("Creature 3"),
                _creature("Creature 4"),
                _creature("Creature 5"),
                _creature("Creature 6"),
            ],
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        _set_main_phase(game)

        engine_cast_spell(game, player, card)
        _resolve_all(game)

        assert player.zones[Zone.BATTLEFIELD].contains(card)
        assert player.mana_pool.total() == 0

    def test_self_affinity_does_not_reduce_colored_mana_requirements(self) -> None:
        game = create_game()
        player = game.players[0]
        card = WitherbloomTheBalancer(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[
                _creature("Creature 1"),
                _creature("Creature 2"),
                _creature("Creature 3"),
                _creature("Creature 4"),
                _creature("Creature 5"),
                _creature("Creature 6"),
                _creature("Creature 7"),
            ],
            hand=[card],
            mana={ManaType.BLACK: 1},
        )
        _set_main_phase(game)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, player, card)

        assert player.zones[Zone.HAND].contains(card)

    def test_grants_affinity_to_your_instants(self) -> None:
        game = create_game()
        player = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        spell = Instant(
            name="Lecture in Decay",
            mana_cost=ManaCost.parse("{3}{R}"),
            owner=player,
            controller=player,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Student 1"), _creature("Student 2")],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        _set_main_phase(game)

        engine_cast_spell(game, player, spell)
        _resolve_all(game)

        assert player.zones[Zone.GRAVEYARD].contains(spell)
        assert player.mana_pool.total() == 0

    def test_grants_affinity_to_your_sorceries(self) -> None:
        game = create_game()
        player = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        spell = Sorcery(
            name="Campus Compost",
            mana_cost=ManaCost.parse("{2}{G}"),
            owner=player,
            controller=player,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Groundskeeper")],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )
        _set_main_phase(game)

        engine_cast_spell(game, player, spell)
        _resolve_all(game)

        assert player.zones[Zone.GRAVEYARD].contains(spell)
        assert player.mana_pool.total() == 0

    def test_granted_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        player = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        spell = Instant(
            name="Single Rot",
            mana_cost=ManaCost.parse("{3}{R}"),
            owner=player,
            controller=player,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[_creature("Enemy 1"), _creature("Enemy 2"), _creature("Enemy 3")],
        )
        _set_main_phase(game)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, player, spell)

        assert player.zones[Zone.HAND].contains(spell)

    def test_granted_affinity_does_not_apply_to_creature_spells(self) -> None:
        game = create_game()
        player = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        creature_spell = Creature(
            name="Not an Instant or Sorcery",
            mana_cost=ManaCost.parse("{3}{G}"),
            base_power=3,
            base_toughness=3,
            owner=player,
            controller=player,
        )

        set_board_state(
            game,
            0,
            battlefield=[
                witherbloom,
                _creature("Creature 1"),
                _creature("Creature 2"),
                _creature("Creature 3"),
            ],
            hand=[creature_spell],
            mana={ManaType.GREEN: 1},
        )
        _set_main_phase(game)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, player, creature_spell)

        assert player.zones[Zone.HAND].contains(creature_spell)

    def test_granted_affinity_does_not_apply_to_opponents_spells(self) -> None:
        game = create_game()
        controller = game.players[0]
        opponent = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=controller, controller=controller)
        spell = Instant(
            name="Unauthorized Research",
            mana_cost=ManaCost.parse("{2}{U}"),
            owner=opponent,
            controller=opponent,
        )

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _creature("Controller Creature")],
        )
        set_board_state(
            game,
            1,
            hand=[spell],
            battlefield=[_creature("Opponent Creature 1"), _creature("Opponent Creature 2")],
            mana={ManaType.BLUE: 1},
        )
        _set_main_phase(game, player_index=1)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, opponent, spell)

        assert opponent.zones[Zone.HAND].contains(spell)
