"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Creature
from engine.casting import resolve_top
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bears(n, prefix="Bear"):
    return [
        Creature(name=f"{prefix} {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


def _cast_emeritus(game, token_to_index):
    p1 = game.players[0]
    card = EmeritusOfTruceSwordsToPlowshares(owner=p1)
    set_board_state(game, 0, hand=[card],
                    mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
    p1._script.append(game.players[token_to_index])  # token's target player
    cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
    return card


def _activate_prepared(game, player, card):
    ability = card.get_activated_abilities()[0]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=card,
            controller=player,
            cost=ability.cost,
            effect=ability.effect,
        ),
    )


class TestEmeritusEnters:
    def test_full_name_constructs_bare(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_etb_creates_flying_inkling_for_target_player(self):
        game = create_game()
        p2 = game.players[1]
        _cast_emeritus(game, token_to_index=1)
        inklings = [
            c for c in game.get_battlefield(p2).get_all()
            if c.name == "Inkling"
        ]
        assert len(inklings) == 1
        assert Keyword.FLYING in inklings[0].keywords
        assert inklings[0].power == 1 and inklings[0].toughness == 1
        assert inklings[0].is_token

    def test_not_prepared_when_counts_equal(self):
        game = create_game()
        set_board_state(game, 1, battlefield=_bears(1))
        # I get the token: me = Emeritus + Inkling = 2; opp = 1.
        card = _cast_emeritus(game, token_to_index=0)
        assert not card.is_prepared
        assert len(game.get_exile(game.players[0])) == 0

    def test_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 1, battlefield=_bears(2))
        # Token to opponent: opp = 3 > me = 1 (Emeritus) -> prepared.
        card = _cast_emeritus(game, token_to_index=1)
        assert card.is_prepared
        copies = [
            c for c in game.get_exile(p1).get_all()
            if c.name == "Swords to Plowshares"
        ]
        assert len(copies) == 1


class TestPreparedCast:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        card = _cast_emeritus(game, token_to_index=1)
        assert card.is_prepared
        return game, p1, p2, card

    def test_cast_copy_exiles_creature_gains_life_unprepares(self):
        game, p1, p2, card = self._prepared_setup()
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        bear = game.get_battlefield(p2).get_all()[0]
        p1._script.append(bear)  # Swords target
        _activate_prepared(game, p1, card)
        resolve_top(game)  # the ability: casts the copy from exile
        resolve_top(game)  # the Swords copy resolves
        assert game.get_exile(p2).contains(bear)
        assert p2.life == 22  # gained life equal to the bear's power
        assert not card.is_prepared
        # The copy ceased to exist: in no zone.
        for player in game.players:
            for zone in (Zone.GRAVEYARD, Zone.EXILE, Zone.STACK):
                assert all(
                    c.name != "Swords to Plowshares"
                    for c in player.zones[zone].get_all()
                )

    def test_cast_requires_white_mana(self):
        game, p1, p2, card = self._prepared_setup()
        set_board_state(game, 0, mana={})
        with pytest.raises(AbilityError):
            _activate_prepared(game, p1, card)
        assert card.is_prepared  # still prepared, copy still exiled

    def test_cannot_cast_when_not_prepared(self):
        game = create_game()
        p1 = game.players[0]
        card = _cast_emeritus(game, token_to_index=0)  # token to me: even
        assert not card.is_prepared
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        with pytest.raises(AbilityError):
            _activate_prepared(game, p1, card)

    def test_copy_ceases_if_emeritus_leaves_battlefield(self):
        from engine.game import destroy

        game, p1, p2, card = self._prepared_setup()
        destroy(game, card)
        resolve_top(game)  # leaves-battlefield trigger
        assert game.get_graveyard(p1).contains(card)
        assert all(
            c.name != "Swords to Plowshares"
            for c in game.get_exile(p1).get_all()
        )
        assert not card.is_prepared
