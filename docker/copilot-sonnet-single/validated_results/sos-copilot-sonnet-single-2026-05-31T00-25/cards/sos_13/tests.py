"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13).

Card requirements:
- EmeritusOfTruce: 3/3 Creature — Cat Cleric {1}{W}{W}
- ETB: target player creates a 1/1 white and black Inkling token with flying
- ETB also: if opponent controls more creatures than you, becomes prepared
- prepared attribute defaults to False
- cast_swords_copy: exiles target creature, controller gains life = creature's power
"""
from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruce,
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
    _etb_effect,
    _cast_swords_copy,
)
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestEmeritusOfTruceProperties:
    """Static card data must match the sos_13 spec."""

    def test_name(self):
        card = EmeritusOfTruce(owner=None)
        assert card.name == "Emeritus of Truce"

    def test_mana_cost(self):
        card = EmeritusOfTruce(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_is_creature(self):
        card = EmeritusOfTruce(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_power(self):
        card = EmeritusOfTruce(owner=None)
        assert card.base_power == 3

    def test_toughness(self):
        card = EmeritusOfTruce(owner=None)
        assert card.base_toughness == 3

    def test_subtypes_cat(self):
        card = EmeritusOfTruce(owner=None)
        assert "Cat" in card.subtypes

    def test_subtypes_cleric(self):
        card = EmeritusOfTruce(owner=None)
        assert "Cleric" in card.subtypes

    def test_prepared_defaults_false(self):
        """prepared attribute must default to False before any ETB fires."""
        card = EmeritusOfTruce(owner=None)
        assert card.prepared is False

    def test_alias_class_is_emeritus(self):
        """EmeritusOfTruceSwordsToPlowshares is an alias for EmeritusOfTruce."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, EmeritusOfTruce)


# ---------------------------------------------------------------------------
# ETB — Inkling token creation
# ---------------------------------------------------------------------------

class TestEmeritusETBInkling:
    """ETB trigger creates a 1/1 white-and-black Inkling token with flying."""

    def _get_new_tokens(self, game, player, bf_before_ids):
        return [
            x for x in game.get_battlefield(player).get_all()
            if id(x) not in bf_before_ids
        ]

    def test_etb_creates_exactly_one_inkling_token(self):
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        bf_before_ids = {id(x) for x in game.get_battlefield(p1).get_all()}
        _etb_effect(game, card)
        new_tokens = self._get_new_tokens(game, p1, bf_before_ids)

        assert len(new_tokens) == 1

    def test_inkling_token_name(self):
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        bf_before_ids = {id(x) for x in game.get_battlefield(p1).get_all()}
        _etb_effect(game, card)
        new_tokens = self._get_new_tokens(game, p1, bf_before_ids)

        assert new_tokens[0].name == "Inkling"

    def test_inkling_token_is_1_1(self):
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        bf_before_ids = {id(x) for x in game.get_battlefield(p1).get_all()}
        _etb_effect(game, card)
        new_tokens = self._get_new_tokens(game, p1, bf_before_ids)
        token = new_tokens[0]

        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_inkling_token_has_flying(self):
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        bf_before_ids = {id(x) for x in game.get_battlefield(p1).get_all()}
        _etb_effect(game, card)
        new_tokens = self._get_new_tokens(game, p1, bf_before_ids)
        token = new_tokens[0]

        assert Keyword.FLYING in token.keywords

    def test_inkling_token_has_inkling_subtype(self):
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        bf_before_ids = {id(x) for x in game.get_battlefield(p1).get_all()}
        _etb_effect(game, card)
        new_tokens = self._get_new_tokens(game, p1, bf_before_ids)
        token = new_tokens[0]

        assert "Inkling" in token.subtypes


# ---------------------------------------------------------------------------
# ETB — prepared condition
# ---------------------------------------------------------------------------

class TestEmeritusETBPrepared:
    """ETB sets prepared=True only when an opponent controls more creatures."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self):
        """Opponent has 3 creatures; controller has 1 (just self) → prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruce(owner=p1, controller=p1)
        opp1 = Creature(name="Opp1", base_power=1, base_toughness=1, owner=p2, controller=p2)
        opp2 = Creature(name="Opp2", base_power=1, base_toughness=1, owner=p2, controller=p2)
        opp3 = Creature(name="Opp3", base_power=1, base_toughness=1, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opp1, opp2, opp3])

        _etb_effect(game, card)

        assert card.prepared is True

    def test_not_prepared_when_opponent_has_fewer_creatures(self):
        """Controller has 2 creatures; opponent has 0 → not prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruce(owner=p1, controller=p1)
        ally = Creature(name="Ally", base_power=2, base_toughness=2, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card, ally])
        set_board_state(game, 1, battlefield=[])

        _etb_effect(game, card)

        assert card.prepared is False

    def test_not_prepared_when_equal_creatures(self):
        """Both players have equal creatures (p1=1, p2=1 before snapshot) → not prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruce(owner=p1, controller=p1)
        opp = Creature(name="Opp", base_power=1, base_toughness=1, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opp])

        _etb_effect(game, card)

        # opponent=1, controller snapshot=1 → equal, not strictly more → not prepared
        assert card.prepared is False


# ---------------------------------------------------------------------------
# cast_swords_copy / SwordsToPlowshares
# ---------------------------------------------------------------------------

class TestSwordsToPlowshares:
    """SwordsToPlowshares exiles a creature and gives its controller life = power."""

    def test_swords_mana_cost(self):
        swords = SwordsToPlowshares(owner=None)
        assert swords.mana_cost == ManaCost.parse("{W}")

    def test_swords_is_instant(self):
        swords = SwordsToPlowshares(owner=None)
        assert isinstance(swords, Instant)

    def test_swords_name(self):
        swords = SwordsToPlowshares(owner=None)
        assert swords.name == "Swords to Plowshares"

    def test_swords_exiles_target_from_battlefield(self):
        """Target creature must be removed from the battlefield after resolution."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Target", base_power=3, base_toughness=3, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        swords = SwordsToPlowshares(owner=p1, controller=p1)
        swords.chosen_targets = [target]
        swords.on_resolve(game)

        assert not game.get_battlefield(p2).contains(target)

    def test_swords_puts_creature_in_exile_zone(self):
        """Exiled creature must appear in the exile zone."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Target", base_power=3, base_toughness=3, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        swords = SwordsToPlowshares(owner=p1, controller=p1)
        swords.chosen_targets = [target]
        swords.on_resolve(game)

        exile_zone = game.get_exile(p2)
        assert exile_zone.contains(target)

    def test_swords_grants_controller_life_equal_to_power(self):
        """Controller of the exiled creature gains life equal to its power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Giant", base_power=5, base_toughness=5, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        swords = SwordsToPlowshares(owner=p1, controller=p1)
        swords.chosen_targets = [target]
        life_before = p2.life
        swords.on_resolve(game)

        assert p2.life == life_before + 5

    def test_swords_life_gain_reflects_power_value(self):
        """Life gain should match the target's power, not a fixed value."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Tiny", base_power=1, base_toughness=4, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        swords = SwordsToPlowshares(owner=p1, controller=p1)
        swords.chosen_targets = [target]
        life_before = p2.life
        swords.on_resolve(game)

        assert p2.life == life_before + 1

    def test_swords_no_life_gain_when_power_is_zero(self):
        """A 0-power creature grants 0 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Wall", base_power=0, base_toughness=4, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        swords = SwordsToPlowshares(owner=p1, controller=p1)
        swords.chosen_targets = [target]
        life_before = p2.life
        swords.on_resolve(game)

        assert p2.life == life_before

    def test_swords_no_op_when_no_targets(self):
        """Resolving without targets must not raise and must leave state unchanged."""
        game = create_game()
        p1 = game.players[0]

        swords = SwordsToPlowshares(owner=p1, controller=p1)
        # No chosen_targets set — should be a silent no-op
        swords.on_resolve(game)  # must not raise


class TestCastSwordsCopy:
    """_cast_swords_copy exiles a creature and unprepares the source."""

    def test_cast_swords_copy_unprepares_source(self):
        """After cast_swords_copy fires, source.prepared must be False."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruce(owner=p1, controller=p1)
        card.prepared = True
        target = Creature(name="Victim", base_power=2, base_toughness=2, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])

        _cast_swords_copy(game, card)

        assert card.prepared is False

    def test_cast_swords_copy_exiles_opponent_creature(self):
        """cast_swords_copy must exile the opponent's creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruce(owner=p1, controller=p1)
        card.prepared = True
        target = Creature(name="Victim", base_power=3, base_toughness=3, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])

        _cast_swords_copy(game, card)

        assert not game.get_battlefield(p2).contains(target)
