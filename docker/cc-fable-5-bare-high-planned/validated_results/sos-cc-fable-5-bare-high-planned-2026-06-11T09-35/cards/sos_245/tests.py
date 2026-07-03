"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import CastingError, cast_spell as engine_cast
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestWitherbloomStatic:
    def test_card_data(self):
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5 and card.base_toughness == 5


class TestWitherbloomOwnAffinity:
    def test_costs_less_per_creature_you_control(self):
        """3 creatures → {6} generic drops to {3}."""
        game = create_game()
        p1 = game.players[0]
        bears = [Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
                 for i in range(3)]
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=bears, hand=[wb],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert p1.zones[Zone.BATTLEFIELD].contains(wb)
        assert p1.mana_pool.total() == 0

    def test_no_creatures_full_cost(self):
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, hand=[wb],
                        mana={ManaType.COLORLESS: 5, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        game.active_player_index = 0
        try:
            engine_cast(game, p1, wb)
            cast_ok = True
        except CastingError:
            cast_ok = False
        assert not cast_ok, "7 mana must not pay {6}{B}{G} with no creatures"

    def test_opponent_creatures_do_not_count(self):
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 1, battlefield=[
            Creature(name="Opp Bear", base_power=2, base_toughness=2)])
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, hand=[wb],
                        mana={ManaType.COLORLESS: 5, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        game.active_player_index = 0
        try:
            engine_cast(game, p1, wb)
            cast_ok = True
        except CastingError:
            cast_ok = False
        assert not cast_ok


class TestWitherbloomGrantsAffinity:
    def test_your_instants_get_affinity(self):
        """Witherbloom + 2 bears = 3 creatures → a {3}{U} instant costs {U}."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=None)
        bears = [Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
                 for i in range(2)]
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0, battlefield=[wb] + bears, hand=[spell],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_affinity_never_reduces_colored_pips(self):
        """A {U}{U} instant still needs both blue pips."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=None)
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{U}{U}"))
        set_board_state(game, 0, battlefield=[wb], hand=[spell],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 5})
        try:
            engine_cast(game, p1, spell)
            cast_ok = True
        except CastingError:
            cast_ok = False
        assert not cast_ok

    def test_opponents_spells_not_reduced(self):
        """An opponent casting an instant gets no reduction from your dragon."""
        game = create_game()
        p2 = game.players[1]
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=[wb])
        spell = Instant(name="Opp Probe", mana_cost=ManaCost.parse("{1}{U}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        try:
            engine_cast(game, p2, spell)
            cast_ok = True
        except CastingError:
            cast_ok = False
        assert not cast_ok, "opponent should still owe the {1}"
