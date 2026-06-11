"""Tests for SOS 220 — Render Speechless.

Render Speechless is a {2}{W}{B} Sorcery with:
- Target opponent reveals their hand. You choose a nonland card from it.
  That player discards that card.
- Put two +1/+1 counters on up to one target creature.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_220.card_impl import RenderSpeechless
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestRenderSpeechlessProperties:
    """Static card data should match the SOS 220 spec."""

    def test_name(self) -> None:
        assert RenderSpeechless(owner=None).name == "Render Speechless"

    def test_mana_cost(self) -> None:
        assert RenderSpeechless(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")


class TestRenderSpeechlessTargeting:
    """Requires targeting an opponent and optionally a creature."""

    def test_get_targets_returns_requirements(self) -> None:
        game = create_game()
        card = RenderSpeechless(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        # Should require at least one target (opponent) and optionally a creature
        assert len(reqs) >= 1


class TestRenderSpeechlessDiscard:
    """Target opponent reveals hand, you choose a nonland card to discard."""

    def test_opponent_discards_nonland_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Give opponent a hand with a nonland card
        creature = Creature(name="Enemy Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        set_board_state(game, 1, hand=[creature])

        spell = RenderSpeechless(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)
        # Opponent's hand should be empty after discard
        hand = game.get_hand(p2)
        assert len(hand) == 0

    def test_land_cards_cannot_be_chosen(self) -> None:
        """Only nonland cards can be chosen for discard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        from engine.card import Card
        land = Card(name="Forest", owner=p2, controller=p2)
        land.card_types = {CardType.LAND}
        set_board_state(game, 1, hand=[land])

        spell = RenderSpeechless(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)
        # Land should remain in hand since no nonland card to choose
        hand = game.get_hand(p2)
        assert len(hand) == 1


class TestRenderSpeechlessCounters:
    """Put two +1/+1 counters on up to one target creature."""

    def test_puts_two_counters_on_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(name="My Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        creature_in_hand = Creature(name="Enemy Creature", owner=p2, controller=p2, base_power=1, base_toughness=1)
        creature_in_hand.card_types = {CardType.CREATURE}
        set_board_state(game, 1, hand=[creature_in_hand])

        spell = RenderSpeechless(owner=p1, controller=p1)
        spell.chosen_targets = [p2, bear]
        before_counters = bear.plus_one_counters
        spell.on_resolve(game)
        assert bear.plus_one_counters == before_counters + 2

    def test_no_creature_target_is_valid(self) -> None:
        """'Up to one' means zero targets for the counter part is legal."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature_in_hand = Creature(name="Enemy Creature", owner=p2, controller=p2, base_power=1, base_toughness=1)
        creature_in_hand.card_types = {CardType.CREATURE}
        set_board_state(game, 1, hand=[creature_in_hand])

        spell = RenderSpeechless(owner=p1, controller=p1)
        spell.chosen_targets = [p2]  # No creature target
        # Should resolve without error
        spell.on_resolve(game)
        # Opponent still discards
        hand = game.get_hand(p2)
        assert len(hand) == 0

    def test_counters_make_creature_bigger(self) -> None:
        """Two +1/+1 counters should increase power and toughness by 2."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(name="My Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        creature_in_hand = Creature(name="Enemy Creature", owner=p2, controller=p2, base_power=1, base_toughness=1)
        creature_in_hand.card_types = {CardType.CREATURE}
        set_board_state(game, 1, hand=[creature_in_hand])

        spell = RenderSpeechless(owner=p1, controller=p1)
        spell.chosen_targets = [p2, bear]
        spell.on_resolve(game)
        # Bear should now be effectively 4/4
        assert bear.power == 4
        assert bear.toughness == 4
