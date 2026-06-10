"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from engine.card import Creature
from engine.casting import cast_spell_free
from engine.types import Keyword, ManaType, Zone
from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from test_utils import (
    _resolve_top_of_stack,
    cast_spell,
    create_game,
    set_board_state,
)

_FULL_NAME = "Emeritus of Truce // Swords to Plowshares"
_MANA = {ManaType.WHITE: 2, ManaType.COLORLESS: 1}


def _swords_in_exile(player):
    return [
        o for o in player.zones[Zone.EXILE].get_all()
        if getattr(o, "name", "") == "Swords to Plowshares"
    ]


class TestETB:
    def test_constructs_bare_with_full_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == _FULL_NAME
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_etb_target_player_creates_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[card], mana=_MANA)
        p1._script.appendleft(p2)  # target player for the token
        cast_spell(game, 0, _FULL_NAME)
        inklings = [
            o for o in p2.zones[Zone.BATTLEFIELD].get_all()
            if getattr(o, "name", "") == "Inkling"
        ]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token

    def test_not_prepared_when_opponent_not_ahead(self) -> None:
        """Opponent ends with 1 creature (the token) vs your Emeritus — not more."""
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[card], mana=_MANA)
        p1._script.appendleft(p2)
        cast_spell(game, 0, _FULL_NAME)
        assert not card.is_prepared
        assert _swords_in_exile(p1) == []

    def test_prepared_when_opponent_controls_more(self) -> None:
        """Opponent with 2 creatures + the token (3) vs your 1 → prepared,
        and a Swords copy appears in your exile."""
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares()
        bears = [Creature(name=f"B{i}", base_power=2, base_toughness=2) for i in range(2)]
        set_board_state(game, 0, hand=[card], mana=_MANA)
        set_board_state(game, 1, battlefield=bears)
        p1._script.appendleft(p2)
        cast_spell(game, 0, _FULL_NAME)
        assert card.is_prepared
        assert len(_swords_in_exile(p1)) == 1


class TestPreparedSpell:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares()
        bears = [Creature(name=f"B{i}", base_power=2, base_toughness=2) for i in range(2)]
        set_board_state(game, 0, hand=[card], mana=_MANA)
        set_board_state(game, 1, battlefield=bears)
        p1._script.appendleft(p2)
        cast_spell(game, 0, _FULL_NAME)
        assert card.is_prepared
        return game, p1, p2, card, _swords_in_exile(p1)[0]

    def test_casting_copy_exiles_creature_gains_life_unprepares(self) -> None:
        game, p1, p2, card, swords = self._prepared_setup()
        bear = p2.zones[Zone.BATTLEFIELD].get_all()[0]
        p1._script.appendleft(bear)  # target for Swords
        cast_spell_free(game, p1, swords, Zone.EXILE)
        # Casting the copy unprepares immediately (rule 722.3c).
        assert not card.is_prepared
        _resolve_top_of_stack(game)
        assert p2.zones[Zone.EXILE].contains(bear)
        assert not p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p2.life == 22  # gains life equal to the bear's power
        # The resolved copy ceases to exist — no Swords card in any zone.
        assert _swords_in_exile(p1) == []
        assert not p1.zones[Zone.GRAVEYARD].get_all()

    def test_copy_ceases_to_exist_if_emeritus_dies(self) -> None:
        game, p1, p2, card, swords = self._prepared_setup()
        from engine.game import destroy

        destroy(game, card)
        assert p1.zones[Zone.GRAVEYARD].contains(card)
        assert not card.is_prepared
        assert _swords_in_exile(p1) == []
