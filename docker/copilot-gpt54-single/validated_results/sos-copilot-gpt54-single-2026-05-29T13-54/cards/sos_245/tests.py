"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Artifact, Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell, get_cost_reduction
from engine.types import Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import create_game, set_board_state


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_deathtouch(self) -> None:
        keywords = WitherbloomTheBalancer(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.DEATHTOUCH in keywords


class TestWitherbloomTheBalancerAffinity:
    """Witherbloom should grant affinity-for-creatures cost reduction correctly."""

    @staticmethod
    def _creature(name: str) -> Creature:
        return Creature(name=name, base_power=1, base_toughness=1)

    @staticmethod
    def _set_sorcery_speed(game, player) -> None:
        game.active_player = player
        game.priority_player_index = game.players.index(player)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    def test_self_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        ally_one = self._creature("Apprentice One")
        ally_two = self._creature("Apprentice Two")
        mana_rock = Artifact(name="Campus Relic")
        opposing_creature = self._creature("Opponent's Creature")

        set_board_state(game, 0, battlefield=[ally_one, ally_two, mana_rock])
        set_board_state(game, 1, battlefield=[opposing_creature])

        assert get_cost_reduction(game, card, p1) == 2

    def test_self_affinity_allows_casting_for_black_green_with_six_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [self._creature(f"Pest {index}") for index in range(6)]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        self._set_sorcery_speed(game, p1)

        engine_cast_spell(game, p1, card)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_battlefield(p1).contains(card) is True
        assert game.get_hand(p1).contains(card) is False

    def test_granted_affinity_counts_only_your_creatures_for_instants(self) -> None:
        game = create_game()
        p1, p2 = game.players
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        ally = self._creature("Research Assistant")
        opposing_one = self._creature("Enemy One")
        opposing_two = self._creature("Enemy Two")
        spell = Instant(
            name="Marsh Lesson",
            mana_cost=ManaCost.parse("{3}{U}"),
            owner=p1,
            controller=p1,
        )

        set_board_state(game, 0, battlefield=[dragon, ally])
        set_board_state(game, 1, battlefield=[opposing_one, opposing_two])
        dragon.register_triggers(game)

        assert get_cost_reduction(game, spell, p1) == 2

    def test_granted_affinity_allows_casting_an_instant_for_only_its_colored_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        ally_one = self._creature("Pest One")
        ally_two = self._creature("Pest Two")
        spell = Instant(
            name="Necrotic Study",
            mana_cost=ManaCost.parse("{3}{U}"),
            owner=p1,
            controller=p1,
        )

        set_board_state(
            game,
            0,
            battlefield=[dragon, ally_one, ally_two],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        dragon.register_triggers(game)

        engine_cast_spell(game, p1, spell)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_graveyard(p1).contains(spell) is True
        assert game.get_hand(p1).contains(spell) is False

    def test_granted_affinity_allows_casting_a_sorcery_for_only_its_colored_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        ally = self._creature("Pest Token")
        spell = Sorcery(
            name="Dark Lecture",
            mana_cost=ManaCost.parse("{2}{B}"),
            owner=p1,
            controller=p1,
        )

        set_board_state(
            game,
            0,
            battlefield=[dragon, ally],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        dragon.register_triggers(game)
        self._set_sorcery_speed(game, p1)

        engine_cast_spell(game, p1, spell)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_graveyard(p1).contains(spell) is True
        assert game.get_hand(p1).contains(spell) is False

    def test_granted_affinity_does_not_reduce_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        ally_one = self._creature("Pest One")
        ally_two = self._creature("Pest Two")
        spell = Creature(
            name="Bog Graduate",
            mana_cost=ManaCost.parse("{2}{G}"),
            base_power=3,
            base_toughness=3,
            owner=p1,
            controller=p1,
        )

        set_board_state(
            game,
            0,
            battlefield=[dragon, ally_one, ally_two],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )
        dragon.register_triggers(game)
        self._set_sorcery_speed(game, p1)

        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, spell)

    def test_granted_affinity_does_not_apply_to_opponents_instants_and_sorceries(self) -> None:
        game = create_game()
        p1, p2 = game.players
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        opponent_one = self._creature("Opponent Pest One")
        opponent_two = self._creature("Opponent Pest Two")
        spell = Instant(
            name="Borrowed Formula",
            mana_cost=ManaCost.parse("{2}{U}"),
            owner=p2,
            controller=p2,
        )

        set_board_state(game, 0, battlefield=[dragon])
        set_board_state(
            game,
            1,
            battlefield=[opponent_one, opponent_two],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        dragon.register_triggers(game)
        game.active_player = p2
        game.priority_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        with pytest.raises(CastingError):
            engine_cast_spell(game, p2, spell)
