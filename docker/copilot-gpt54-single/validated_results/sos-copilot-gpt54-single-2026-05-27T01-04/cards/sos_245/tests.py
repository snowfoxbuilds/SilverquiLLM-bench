"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, Supertype
from test_utils import create_game, set_board_state


def _creature(name: str) -> Creature:
    """Create a simple creature permanent for battlefield counting."""
    return Creature(name=name, base_power=2, base_toughness=2)


def _instant(name: str = "Training Instant", cost: str = "{3}{U}") -> Instant:
    """Create a simple instant spell for cost-reduction checks."""
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _sorcery(name: str = "Training Sorcery", cost: str = "{4}{B}") -> Sorcery:
    """Create a simple sorcery spell for cost-reduction checks."""
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_a_legendary_elder_dragon_creature_named_witherbloom_the_balancer(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Witherbloom, the Balancer"
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_has_expected_mana_cost_keywords_stats_and_rules_text(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert card.rules_text == (
            "Affinity for creatures (This spell costs {1} less to cast for each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures."
        )


class TestWitherbloomTheBalancerAffinity:
    """Witherbloom itself should have affinity for creatures."""

    def test_self_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        your_first = _creature("Your First Creature")
        your_second = _creature("Your Second Creature")
        opposing_creature = _creature("Opposing Creature")

        set_board_state(game, 0, battlefield=[your_first, your_second])
        set_board_state(game, 1, battlefield=[opposing_creature])

        assert get_cost_reduction(game, card, p1) == 2

    def test_self_affinity_is_clamped_to_the_generic_portion_of_its_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        creatures = [_creature(f"Creature {index}") for index in range(8)]
        set_board_state(game, 0, battlefield=creatures)

        assert get_cost_reduction(game, card, p1) == 6


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries."""

    def test_granted_affinity_counts_witherbloom_itself_for_your_instants(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _instant(cost="{2}{U}")

        set_board_state(game, 0, battlefield=[witherbloom])

        assert get_cost_reduction(game, spell, p1) == 1

    def test_granted_affinity_applies_to_your_sorcery_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        assistant = _creature("Assistant")
        spell = _sorcery(cost="{4}{B}")

        set_board_state(game, 0, battlefield=[witherbloom, assistant])

        assert get_cost_reduction(game, spell, p1) == 2

    def test_granted_affinity_does_not_reduce_your_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        assistant = _creature("Assistant")
        creature_spell = Creature(
            name="Training Creature",
            mana_cost=ManaCost.parse("{4}{G}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(game, 0, battlefield=[witherbloom, assistant])

        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_granted_affinity_does_not_reduce_opponents_instants_or_sorceries(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        their_first = _creature("Their First Creature")
        their_second = _creature("Their Second Creature")
        opposing_spell = _instant(cost="{3}{U}")

        set_board_state(game, 0, battlefield=[witherbloom])
        set_board_state(game, 1, battlefield=[their_first, their_second])

        assert get_cost_reduction(game, opposing_spell, p2) == 0

    def test_granted_affinity_is_clamped_to_the_generic_portion_of_the_recipient_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_creature(f"Creature {index}") for index in range(4)]
        spell = _instant(cost="{1}{B}")

        set_board_state(game, 0, battlefield=[witherbloom, *creatures])

        assert get_cost_reduction(game, spell, p1) == 1
