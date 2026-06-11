"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import (
    _resolve_top_of_stack,
    cast_spell,
    create_game,
    set_board_state,
)

EMERITUS_NAME = "Emeritus of Truce // Swords to Plowshares"
EMERITUS_MANA = {ManaType.COLORLESS: 1, ManaType.WHITE: 2}


def _cast_emeritus(game, token_to_player, opponent_creatures):
    """Cast the Emeritus through the engine with a scripted token target."""
    p1 = game.players[0]
    emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
    set_board_state(game, 1, battlefield=opponent_creatures)
    set_board_state(game, 0, hand=[emeritus], mana=dict(EMERITUS_MANA))
    p1._script.append(token_to_player)
    cast_spell(game, 0, EMERITUS_NAME)
    return emeritus


def _activate_prepared_cast(game, emeritus, player, target):
    ability = emeritus.get_activated_abilities()[0]
    instance = ActivatedAbilityInstance(
        source=emeritus,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        description=ability.description,
    )
    player._script.append(target)
    activate_ability(game, player, instance)
    _resolve_top_of_stack(game)


class TestEmeritusStatics:
    def test_constructs_bare_with_full_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == EMERITUS_NAME
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes


class TestEmeritusEnterTrigger:
    def test_target_player_creates_inkling(self):
        game = create_game()
        p2 = game.players[1]
        _cast_emeritus(game, token_to_player=p2, opponent_creatures=[])
        tokens = [
            c for c in game.get_battlefield(p2).get_all()
            if getattr(c, "name", "") == "Inkling"
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.base_power == 1 and token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token

    def test_not_prepared_when_opponent_has_fewer_creatures(self):
        game = create_game()
        p1 = game.players[0]
        # Token to me: I end with Emeritus + Inkling, opponent has 0.
        emeritus = _cast_emeritus(game, token_to_player=p1,
                                  opponent_creatures=[])
        assert emeritus.is_prepared is False
        assert len(game.get_exile(p1)) == 0

    def test_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p1, p2 = game.players
        bears = [
            Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(2)
        ]
        # Token to opponent: they end with 3 creatures vs my 1.
        emeritus = _cast_emeritus(game, token_to_player=p2,
                                  opponent_creatures=bears)
        assert emeritus.is_prepared is True
        # The Swords copy already sits in exile (rule 722.3c).
        exiled = game.get_exile(p1).get_all()
        assert [c.name for c in exiled] == ["Swords to Plowshares"]


class TestPreparedCast:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        bears = [
            Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(2)
        ]
        emeritus = _cast_emeritus(game, token_to_player=p2,
                                  opponent_creatures=bears)
        assert emeritus.is_prepared
        return game, p1, p2, emeritus, bears

    def test_cast_copy_exiles_creature_and_unprepares(self):
        game, p1, p2, emeritus, bears = self._prepared_setup()
        p1.mana_pool.add(ManaType.WHITE, 1)
        target = bears[0]
        _activate_prepared_cast(game, emeritus, p1, target)
        # Target exiled; its controller gained life equal to its power.
        assert game.get_exile(p2).contains(target)
        assert p2.life == 22
        # Unprepared, and the copy is gone from every zone.
        assert emeritus.is_prepared is False
        for player in game.players:
            for zone in (Zone.EXILE, Zone.GRAVEYARD, Zone.STACK):
                assert not any(
                    getattr(c, "name", "") == "Swords to Plowshares"
                    for c in player.zones[zone].get_all()
                )

    def test_cannot_cast_copy_twice(self):
        game, p1, p2, emeritus, bears = self._prepared_setup()
        p1.mana_pool.add(ManaType.WHITE, 2)
        _activate_prepared_cast(game, emeritus, p1, bears[0])
        with pytest.raises(AbilityError):
            _activate_prepared_cast(game, emeritus, p1, bears[1])

    def test_cannot_cast_without_white_mana(self):
        game, p1, p2, emeritus, bears = self._prepared_setup()
        assert p1.mana_pool.total() == 0
        with pytest.raises(AbilityError):
            _activate_prepared_cast(game, emeritus, p1, bears[0])
        assert emeritus.is_prepared  # still prepared, copy still castable
        assert game.get_exile(p1).contains(emeritus._prepared_copy)

    def test_copy_ceases_to_exist_when_emeritus_dies(self):
        from engine.game import destroy

        game, p1, p2, emeritus, bears = self._prepared_setup()
        destroy(game, emeritus)
        assert game.get_graveyard(p1).contains(emeritus)
        assert not any(
            getattr(c, "name", "") == "Swords to Plowshares"
            for c in game.get_exile(p1).get_all()
        )
