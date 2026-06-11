"""Tests for The Dawning Archaic (sos_1)."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class PingSpell(Instant):
    """Test instant: deals 2 damage to the non-active player on resolve."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Ping Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        deal_damage(game, self, game.non_active_player, 2)


def _resolve_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_static(self):
        c = TheDawningArchaic(owner=None)
        assert c.name == "The Dawning Archaic"
        assert c.mana_cost == ManaCost.parse("{10}")
        assert Keyword.REACH in c.keywords
        assert c.base_power == 7 and c.base_toughness == 7
        assert Supertype.LEGENDARY in c.supertypes


class TestCostReduction:
    def test_three_spells_reduce_cost(self):
        game = create_game()
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{U}")) for i in range(3)]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        bf = game.get_battlefield(game.players[0])
        assert any(getattr(c, "name", "") == "The Dawning Archaic" for c in bf.get_all())

    def test_insufficient_reduction_fails(self):
        game = create_game()
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{U}")) for i in range(2)]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})  # cost would be 10-2 = 8 > 7
        with pytest.raises(Exception):
            cast_spell(game, 0, "The Dawning Archaic")


class TestAttackTrigger:
    def test_casts_from_graveyard_and_exiles(self):
        game = create_game(scripts=([True], []))  # p0 says "yes" to the may
        p0, p1 = game.players
        archaic = TheDawningArchaic(owner=None)
        ping = PingSpell()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[ping])
        archaic.summoning_sick = False
        archaic.register_triggers(game)  # mirror ETB registration

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)

        # Ping resolved (opponent took 2), and it was exiled, not in graveyard.
        assert p1.life == 18
        assert game.get_exile(p0).contains(ping)
        assert not game.get_graveyard(p0).contains(ping)

    def test_decline_the_may(self):
        game = create_game(scripts=([False], []))  # decline
        p0, p1 = game.players
        archaic = TheDawningArchaic(owner=None)
        ping = PingSpell()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[ping])
        archaic.summoning_sick = False
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)
        # Nothing happened — ping still in graveyard, no damage.
        assert p1.life == 20
        assert game.get_graveyard(p0).contains(ping)

    def test_empty_graveyard_noop(self):
        game = create_game(scripts=([], []))
        p0, p1 = game.players
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[archaic])
        archaic.summoning_sick = False
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)  # no candidates; must not error or prompt
        assert p1.life == 20
