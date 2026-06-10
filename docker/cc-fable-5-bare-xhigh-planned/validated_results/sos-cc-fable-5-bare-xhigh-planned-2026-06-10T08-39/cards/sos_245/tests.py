"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Zone
from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


class TestOwnAffinity:
    def test_costs_one_less_per_creature(self) -> None:
        """3 creatures → {3}{B}{G}."""
        game = create_game()
        card = WitherbloomTheBalancer()
        creatures = [
            Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(3)
        ]
        set_board_state(
            game, 0, battlefield=creatures, hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(card)
        assert game.players[0].mana_pool.total() == 0

    def test_no_creatures_full_cost(self) -> None:
        """No creatures → full {6}{B}{G}; {5}{B}{G} worth of mana fails."""
        game = create_game()
        card = WitherbloomTheBalancer()
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 5},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_keywords(self) -> None:
        card = WitherbloomTheBalancer()
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords


class TestGrantedAffinity:
    def test_instants_you_cast_get_affinity(self) -> None:
        """Witherbloom + 2 creatures → your {3}{U} instant costs just {U}."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        others = [
            Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(2)
        ]
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(
            game, 0, battlefield=[wb] + others, hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        cast_spell(game, 0, "Probe")
        assert game.players[0].zones[Zone.GRAVEYARD].contains(spell)

    def test_affinity_never_reduces_colored_pips(self) -> None:
        """{1}{U} with 3 creatures → still needs the {U}."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        others = [
            Creature(name=f"C{i}", base_power=1, base_toughness=1) for i in range(2)
        ]
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{1}{U}"))
        set_board_state(
            game, 0, battlefield=[wb] + others, hand=[spell],
            mana={ManaType.COLORLESS: 2},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Probe")

    def test_opponent_spells_do_not_benefit(self) -> None:
        """Witherbloom only grants affinity to its controller's spells."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 0, battlefield=[wb])
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Probe")
