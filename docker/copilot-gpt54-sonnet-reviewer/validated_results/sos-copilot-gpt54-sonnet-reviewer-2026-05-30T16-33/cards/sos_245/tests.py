"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Enchantment, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_name_mana_cost_rules_text_and_affinity_metadata(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.rules_text == (
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures."
        )
        assert "Affinity" in getattr(card, "mechanic_keywords", set())

    def test_is_legendary_elder_dragon_with_flying_deathtouch_and_five_five(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestWitherbloomTheBalancerSelfAffinity:
    """The dragon itself should have affinity for creatures."""

    def test_cost_reduction_counts_only_your_creatures_on_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[
                Creature(name="Pest", base_power=1, base_toughness=1),
                Creature(name="Bat", base_power=1, base_toughness=1),
                Enchantment(name="Dormant Lesson"),
            ],
        )
        set_board_state(
            game,
            1,
            battlefield=[Creature(name="Bear", base_power=2, base_toughness=2)],
        )

        assert card.cost_reduction(game) == 2

    def test_casting_with_six_other_creatures_can_reduce_the_generic_cost_to_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Creature {idx}", base_power=1, base_toughness=1)
            for idx in range(6)
        ]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(card)
        assert not game.get_hand(p1).contains(card)

    def test_casting_still_requires_colored_mana_after_affinity_reduces_generic_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Creature {idx}", base_power=1, base_toughness=1)
            for idx in range(6)
        ]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={ManaType.GREEN: 1},
        )

        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries."""

    def test_grants_affinity_for_creatures_to_your_instant_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Instant(name="Bog Lesson", mana_cost=ManaCost.parse("{3}{B}"))

        set_board_state(
            game,
            0,
            battlefield=[
                card,
                Creature(name="Pest", base_power=1, base_toughness=1),
                Creature(name="Leech", base_power=1, base_toughness=1),
            ],
        )

        assert card.get_affinity_reduction_for(game, p1, spell) == 3

    def test_grants_affinity_for_creatures_to_your_sorcery_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Sorcery(name="Mulch Notes", mana_cost=ManaCost.parse("{2}{G}"))

        set_board_state(
            game,
            0,
            battlefield=[
                card,
                Creature(name="Pest", base_power=1, base_toughness=1),
            ],
        )

        assert card.get_affinity_reduction_for(game, p1, spell) == 2

    def test_does_not_grant_affinity_to_noninstant_nonsorcery_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Creature(
            name="Campus Scavenger",
            mana_cost=ManaCost.parse("{3}{G}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(game, 0, battlefield=[card])

        assert card.get_affinity_reduction_for(game, p1, spell) is None

    def test_does_not_grant_affinity_to_an_opponents_instant_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Instant(
            name="Opponent's Lesson",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{U}"),
        )

        set_board_state(game, 0, battlefield=[card])

        assert card.get_affinity_reduction_for(game, p2, spell) is None

    def test_does_not_grant_affinity_while_not_on_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Instant(name="Absent Lecture", mana_cost=ManaCost.parse("{2}{B}"))

        set_board_state(game, 0, hand=[card])

        assert card.get_affinity_reduction_for(game, p1, spell) is None

    def test_casting_an_instant_uses_the_battlefield_grant_to_reduce_its_generic_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Instant(name="Bog Lesson", mana_cost=ManaCost.parse("{3}{B}"))

        set_board_state(
            game,
            0,
            battlefield=[
                dragon,
                Creature(name="Pest", base_power=1, base_toughness=1),
                Creature(name="Leech", base_power=1, base_toughness=1),
            ],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )

        cast_spell(game, 0, "Bog Lesson")

        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_hand(p1).contains(spell)

    def test_casting_a_creature_spell_does_not_get_the_battlefield_grant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = Creature(
            name="Campus Scavenger",
            mana_cost=ManaCost.parse("{3}{G}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(
            game,
            0,
            battlefield=[
                dragon,
                Creature(name="Pest", base_power=1, base_toughness=1),
                Creature(name="Leech", base_power=1, base_toughness=1),
            ],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )

        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Campus Scavenger")
