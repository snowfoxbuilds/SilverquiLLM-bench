"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer()
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.base_power == 5 and card.base_toughness == 5


class TestOwnAffinity:
    def test_costs_one_less_per_creature(self) -> None:
        """3 creatures → {6}{B}{G} becomes {3}{B}{G}."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(
            game, 0,
            battlefield=[_bear("A"), _bear("B"), _bear("C")],
            hand=[wb],
            mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(wb)
        assert game.players[0].mana_pool.total() == 0

    def test_no_creatures_full_cost(self) -> None:
        """0 creatures → full {6}{B}{G}; 5 generic available is not enough."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(
            game, 0, hand=[wb],
            mana={ManaType.COLORLESS: 5, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestGrantedAffinity:
    def test_your_instants_cost_less(self) -> None:
        """Witherbloom + 2 bears = 3 creatures → {4}{U} instant costs {1}{U}."""
        game = create_game()
        spell = Instant(name="Big Draw", mana_cost=ManaCost.parse("{4}{U}"))
        set_board_state(
            game, 0,
            battlefield=[WitherbloomTheBalancer(), _bear("A"), _bear("B")],
            hand=[spell],
            mana={ManaType.COLORLESS: 1, ManaType.BLUE: 1},
        )
        cast_spell(game, 0, "Big Draw")
        assert game.players[0].zones[Zone.GRAVEYARD].contains(spell)
        assert game.players[0].mana_pool.total() == 0

    def test_opponent_spells_unaffected(self) -> None:
        """An opponent's instant gets no reduction from your Witherbloom."""
        game = create_game()
        spell = Instant(name="Opposing Bolt", mana_cost=ManaCost.parse("{2}{R}"))
        set_board_state(game, 0, battlefield=[WitherbloomTheBalancer(), _bear()])
        set_board_state(
            game, 1, hand=[spell],
            mana={ManaType.COLORLESS: 1, ManaType.RED: 1},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Opposing Bolt")

    def test_creature_spells_not_granted_affinity(self) -> None:
        """The grant applies to instants/sorceries only, not creature spells."""
        game = create_game()
        creature_spell = _bear("Castable Bear")
        creature_spell.mana_cost = ManaCost.parse("{3}")
        set_board_state(
            game, 0,
            battlefield=[WitherbloomTheBalancer(), _bear("A")],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 2},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Castable Bear")
