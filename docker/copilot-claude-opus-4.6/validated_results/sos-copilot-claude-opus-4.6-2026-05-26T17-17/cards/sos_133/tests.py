"""Tests for SOS 133 — Tackle Artist.

A 4/3 Orc Sorcerer for {3}{R} with Trample.
Opus — Whenever you cast an instant or sorcery spell, put a +1/+1 counter on
this creature. If five or more mana was spent to cast that spell, put two
+1/+1 counters on this creature instead.
"""

from __future__ import annotations

from cards.sos.sos_133.card_impl import TackleArtist
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTackleArtistProperties:
    """Static card data should match the SOS 133 spec."""

    def test_is_creature(self) -> None:
        card = TackleArtist(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TackleArtist(owner=None)
        assert card.name == "Tackle Artist"

    def test_mana_cost(self) -> None:
        card = TackleArtist(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}")

    def test_power_toughness(self) -> None:
        card = TackleArtist(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_has_trample(self) -> None:
        card = TackleArtist(owner=None)
        assert Keyword.TRAMPLE in card.keywords


class TestTackleArtistOpus:
    """Opus trigger: +1/+1 counter on instant/sorcery cast."""

    def test_gains_one_counter_on_cheap_spell(self) -> None:
        """Casting an instant/sorcery with less than 5 mana spent gives 1 counter."""
        game = create_game()
        p1 = game.players[0]
        card = TackleArtist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        counters_before = card.plus_one_counters
        # Simulate triggering opus with a spell that cost less than 5 mana
        card.on_spell_cast(game, mana_spent=3)
        assert card.plus_one_counters == counters_before + 1

    def test_gains_two_counters_on_expensive_spell(self) -> None:
        """Casting an instant/sorcery with 5+ mana spent gives 2 counters instead."""
        game = create_game()
        p1 = game.players[0]
        card = TackleArtist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        counters_before = card.plus_one_counters
        # Simulate triggering opus with a spell that cost 5 or more mana
        card.on_spell_cast(game, mana_spent=5)
        assert card.plus_one_counters == counters_before + 2

    def test_gains_two_counters_on_six_mana_spell(self) -> None:
        """Verify 'five or more' — 6 mana should also give 2 counters."""
        game = create_game()
        p1 = game.players[0]
        card = TackleArtist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        counters_before = card.plus_one_counters
        card.on_spell_cast(game, mana_spent=6)
        assert card.plus_one_counters == counters_before + 2

    def test_exactly_four_mana_gives_one_counter(self) -> None:
        """Boundary: 4 mana is less than 5, so only 1 counter."""
        game = create_game()
        p1 = game.players[0]
        card = TackleArtist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        counters_before = card.plus_one_counters
        card.on_spell_cast(game, mana_spent=4)
        assert card.plus_one_counters == counters_before + 1

    def test_multiple_spells_accumulate_counters(self) -> None:
        """Multiple spell casts should accumulate counters."""
        game = create_game()
        p1 = game.players[0]
        card = TackleArtist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.on_spell_cast(game, mana_spent=2)  # +1
        card.on_spell_cast(game, mana_spent=5)  # +2
        assert card.plus_one_counters == 3
