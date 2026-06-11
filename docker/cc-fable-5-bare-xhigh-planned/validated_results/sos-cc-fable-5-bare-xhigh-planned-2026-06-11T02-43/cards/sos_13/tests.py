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
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _ability_instance(card):
    ability = card.get_activated_abilities()[0]
    return ActivatedAbilityInstance(
        source=card,
        controller=card.controller,
        cost=ability.cost,
        effect=ability.effect,
        description=ability.description,
    )


class TestProperties:
    def test_constructs_bare_with_full_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert not card.is_prepared


class TestEnterTheBattlefield:
    def test_token_and_becomes_prepared(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2")])

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # ETB choice: the opponent is the targeted player for the token.
        p1._script.append(p2)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        inklings = [c for c in game.get_battlefield(p2).get_all()
                    if c.name == "Inkling"]
        assert len(inklings) == 1
        assert inklings[0].is_token
        assert Keyword.FLYING in inklings[0].keywords
        assert inklings[0].power == 1 and inklings[0].toughness == 1

        # Opponent controls 3 creatures vs our 1 → prepared, copy in exile.
        assert emeritus.is_prepared
        swords_in_exile = [c for c in game.get_exile(p1).get_all()
                           if c.name == "Swords to Plowshares"]
        assert len(swords_in_exile) == 1

    def test_not_prepared_when_not_outnumbered(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("B1")])

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # Token to ourselves: we end at 2 creatures vs opponent's 1.
        p1._script.append(p1)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        assert not emeritus.is_prepared
        assert game.get_exile(p1).get_all() == []


class TestPreparedCast:
    def _prepared_game(self):
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2")])
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        p1._script.append(p2)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        assert emeritus.is_prepared
        return game, p1, p2, emeritus

    def test_cast_copy_exiles_creature_and_unprepares(self) -> None:
        game, p1, p2, emeritus = self._prepared_game()
        bear = next(c for c in game.get_battlefield(p2).get_all()
                    if c.name == "B1")
        p1.mana_pool.add(ManaType.WHITE, 1)

        activate_ability(game, p1, _ability_instance(emeritus))
        # ability resolves, then the Swords copy is cast targeting B1.
        p1._script.extend(["pass", bear, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert game.get_exile(p2).contains(bear)        # exiled
        assert p2.life == 22                            # gained 2 (its power)
        assert not emeritus.is_prepared                 # unprepared by casting
        # The resolved copy ceased to exist — not in any graveyard/exile.
        assert all(c.name != "Swords to Plowshares"
                   for c in game.get_graveyard(p1).get_all())
        assert all(c.name != "Swords to Plowshares"
                   for c in game.get_exile(p1).get_all())
        assert p1.mana_pool.total() == 0                # paid {W}

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        with pytest.raises(AbilityError):
            activate_ability(game, p1, _ability_instance(emeritus))

    def test_cannot_cast_without_mana(self) -> None:
        game, p1, p2, emeritus = self._prepared_game()
        assert p1.mana_pool.total() == 0
        with pytest.raises(AbilityError):
            activate_ability(game, p1, _ability_instance(emeritus))
        assert emeritus.is_prepared                     # still prepared


class TestSwordsHelper:
    def test_no_creature_no_cast(self) -> None:
        game = create_game()
        swords = SwordsToPlowshares()
        assert swords.can_cast(game) is False
