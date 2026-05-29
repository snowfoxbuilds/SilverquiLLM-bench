"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import cast_spell, create_game, set_board_state


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the card spec."""

    def test_is_a_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_is_a_legendary_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_deathtouch_and_affinity(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert hasattr(Keyword, "AFFINITY")
        assert Keyword.AFFINITY in card.keywords


class TestWitherbloomTheBalancerOwnAffinity:
    """Witherbloom itself should have affinity for creatures while being cast."""

    @staticmethod
    def _creatures(count: int) -> list[Creature]:
        return [
            Creature(name=f"Creature {i}", base_power=1, base_toughness=1)
            for i in range(count)
        ]

    def test_cost_reduction_counts_each_creature_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=self._creatures(3))

        assert get_cost_reduction(game, card, p1) == 3

    def test_cost_reduction_ignores_opponents_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=self._creatures(1))
        set_board_state(game, 1, battlefield=self._creatures(4))

        assert get_cost_reduction(game, card, p1) == 1

    def test_cost_reduction_is_capped_at_six_generic_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=self._creatures(10))

        assert get_cost_reduction(game, card, p1) == 6

    def test_can_be_cast_for_only_black_and_green_when_you_control_six_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=self._creatures(6),
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(card)


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries."""

    @staticmethod
    def _creatures(count: int) -> list[Creature]:
        return [
            Creature(name=f"Creature {i}", base_power=1, base_toughness=1)
            for i in range(count)
        ]

    @staticmethod
    def _instant(name: str, mana_cost: str) -> Instant:
        return Instant(name=name, mana_cost=ManaCost.parse(mana_cost))

    @staticmethod
    def _sorcery(name: str, mana_cost: str) -> Sorcery:
        return Sorcery(name=name, mana_cost=ManaCost.parse(mana_cost))

    def test_grants_your_instant_spells_affinity_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = self._instant("Sudden Growth", "{3}{G}")

        set_board_state(game, 0, battlefield=[witherbloom, *self._creatures(2)])

        assert get_cost_reduction(game, spell, p1) == 3

    def test_grants_your_sorcery_spells_affinity_in_the_casting_pipeline(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = self._sorcery("Witherbloom Lesson", "{3}{G}")

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, *self._creatures(2)],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom Lesson")

        assert game.get_graveyard(p1).contains(spell)

    def test_reduces_only_your_instants_and_sorceries_not_your_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant_spell = self._instant("Sudden Growth", "{3}{G}")
        creature_spell = Creature(
            name="Hill Troll",
            mana_cost=ManaCost.parse("{3}{G}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(game, 0, battlefield=[witherbloom, *self._creatures(2)])

        assert get_cost_reduction(game, instant_spell, p1) == 3
        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_granted_affinity_turns_on_only_while_witherbloom_is_on_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = self._instant("Sudden Growth", "{3}{G}")

        set_board_state(game, 0, battlefield=self._creatures(3))

        assert get_cost_reduction(game, spell, p1) == 0

        set_board_state(game, 0, battlefield=[witherbloom, *self._creatures(2)])

        assert get_cost_reduction(game, spell, p1) == 3

    def test_reduction_applies_only_to_your_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_spell = self._instant("Your Trick", "{3}{G}")
        opponent_spell = self._instant("Enemy Trick", "{3}{U}")

        set_board_state(game, 0, battlefield=[witherbloom, *self._creatures(2)])
        set_board_state(game, 1, battlefield=self._creatures(3))

        assert get_cost_reduction(game, your_spell, p1) == 3
        assert get_cost_reduction(game, opponent_spell, p2) == 0
