"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import Keyword, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state

FULL_NAME = "Emeritus of Truce // Swords to Plowshares"


def _bears(n: int, prefix: str = "Bear") -> list[Creature]:
    return [
        Creature(name=f"{prefix} {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


def _cast_emeritus(game, token_target_index=0, opp_creatures=0):
    p1 = game.players[0]
    if opp_creatures:
        set_board_state(game, 1, battlefield=_bears(opp_creatures))
    emeritus = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(
        game, 0, hand=[emeritus],
        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
    )
    cast_spell(game, 0, FULL_NAME, targets=[game.players[token_target_index]])
    return emeritus


class TestEmeritus:
    def test_constructs_bare_with_full_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == FULL_NAME
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_etb_creates_inkling_for_target_player(self):
        game = create_game()
        p2 = game.players[1]
        _cast_emeritus(game, token_target_index=1)
        inklings = [
            c for c in game.get_battlefield(p2).get_all() if c.name == "Inkling"
        ]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token

    def test_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p1 = game.players[0]
        # Opponent: 3 bears (+0 tokens). You: Emeritus + your Inkling = 2.
        emeritus = _cast_emeritus(game, token_target_index=0, opp_creatures=3)
        assert emeritus.prepared
        # Rule 722.3c: the Swords copy exists in exile while prepared.
        copies = [
            c for c in game.get_exile(p1).get_all()
            if c.name == "Swords to Plowshares"
        ]
        assert len(copies) == 1

    def test_not_prepared_when_counts_equal(self):
        game = create_game()
        p1 = game.players[0]
        # Opponent: 1 bear + your token to them = 2. You: Emeritus = 1...
        # give the token to yourself: you 2, opponent 1 -> not prepared.
        emeritus = _cast_emeritus(game, token_target_index=0, opp_creatures=2)
        # You: Emeritus + Inkling = 2; opponent 2 -> not strictly more.
        assert not emeritus.prepared
        assert game.get_exile(p1).get_all() == []

    def test_cast_prepared_copy_exiles_creature_and_unprepares(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = _cast_emeritus(game, token_target_index=0, opp_creatures=3)
        assert emeritus.prepared
        target = game.get_battlefield(p2).get_all()[0]  # a 2/2 bear

        p1.mana_pool.add(ManaType.WHITE, 1)
        ability = emeritus.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(
            source=emeritus, controller=p1, cost=ability.cost, effect=ability.effect,
        )
        activate_ability(game, p1, inst)
        p1._script.extend(["pass", target, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert game.get_exile(p2).contains(target)
        assert p2.life == 22  # gained life equal to its power (2)
        assert not emeritus.prepared
        # The copy is gone — not in exile, not in a graveyard.
        for p in game.players:
            assert all(
                c.name != "Swords to Plowshares"
                for c in list(game.get_exile(p).get_all())
                + list(game.get_graveyard(p).get_all())
            )

    def test_copy_cast_requires_mana(self):
        game = create_game()
        p1 = game.players[0]
        emeritus = _cast_emeritus(game, token_target_index=0, opp_creatures=3)
        assert emeritus.prepared
        assert p1.mana_pool.total() == 0  # all spent on the Emeritus
        ability = emeritus.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(
            source=emeritus, controller=p1, cost=ability.cost, effect=ability.effect,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, p1, inst)
        assert emeritus.prepared  # still prepared

    def test_copy_ceases_when_emeritus_dies(self):
        from engine.game import destroy

        game = create_game()
        p1 = game.players[0]
        emeritus = _cast_emeritus(game, token_target_index=0, opp_creatures=3)
        assert emeritus.prepared
        destroy(game, emeritus)
        # Leaves-battlefield trigger is on the stack; resolve it.
        p1._script.extend(["pass"])
        game.players[1]._script.extend(["pass"])
        priority_loop(game)
        assert game.get_exile(p1).get_all() == []
        assert not emeritus.prepared
