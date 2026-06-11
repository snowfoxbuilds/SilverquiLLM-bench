"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state

FULL_NAME = "Emeritus of Truce // Swords to Plowshares"
_CAST_MANA = {ManaType.WHITE: 2, ManaType.COLORLESS: 1}


def _bears(n: int) -> list[Creature]:
    return [Creature(name=f"Bear {i}", base_power=2, base_toughness=2) for i in range(n)]


class TestStaticProperties:
    def test_full_card_name_constructs_bare(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == FULL_NAME
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3
        assert card.subtypes == {"Cat", "Cleric"}
        assert not card.prepared


class TestEntersTheBattlefield:
    def test_target_player_creates_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares()], mana=dict(_CAST_MANA))
        p1._script.extend([p2])  # token goes to the opponent
        cast_spell(game, 0, FULL_NAME)
        inklings = [c for c in game.get_battlefield(p2).get_all() if c.name == "Inkling"]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.base_power == 1 and token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token

    def test_not_prepared_when_counts_tie(self) -> None:
        """Token to opponent makes it 1-1: not strictly more -> unprepared."""
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus], mana=dict(_CAST_MANA))
        p1._script.extend([p2])
        cast_spell(game, 0, FULL_NAME)
        assert not emeritus.prepared
        assert len(game.get_exile(p1).get_all()) == 0

    def test_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus], mana=dict(_CAST_MANA))
        p1._script.extend([p1])  # token to self: 2 vs 3 -> still fewer
        cast_spell(game, 0, FULL_NAME)
        assert emeritus.prepared
        # The prepare-spell copy was created in exile.
        copies = [c for c in game.get_exile(p1).get_all() if c.name == "Swords to Plowshares"]
        assert len(copies) == 1


class TestCastingThePreparedCopy:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus], mana=dict(_CAST_MANA))
        p1._script.extend([p1])
        cast_spell(game, 0, FULL_NAME)
        assert emeritus.prepared
        copy = next(
            c for c in game.get_exile(p1).get_all() if c.name == "Swords to Plowshares"
        )
        return game, p1, p2, emeritus, copy

    def test_cast_copy_exiles_creature_gains_life_unprepares(self) -> None:
        game, p1, p2, emeritus, copy = self._prepared_setup()
        bear = game.get_battlefield(p2).get_all()[0]
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p1._script.extend([bear])
        engine_cast_spell(game, p1, copy, from_zone=Zone.EXILE)
        assert not emeritus.prepared  # unprepared as soon as it's cast
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.get_exile(p2).contains(bear)
        assert p2.life == 22  # gained life equal to the bear's power
        # The resolved copy ceased to exist: not in graveyard or exile.
        assert not game.get_graveyard(p1).contains(copy)
        assert not game.get_exile(p1).contains(copy)

    def test_copy_requires_its_mana_cost(self) -> None:
        game, p1, p2, emeritus, copy = self._prepared_setup()
        bear = game.get_battlefield(p2).get_all()[0]
        set_board_state(game, 0, mana={})  # no mana
        p1._script.extend([bear])
        try:
            engine_cast_spell(game, p1, copy, from_zone=Zone.EXILE)
            raised = False
        except Exception:
            raised = True
        assert raised, "the prepare-spell copy costs {W}; it is not free"
        assert emeritus.prepared  # cast failed: still prepared
        assert game.get_exile(p1).contains(copy)

    def test_copy_vanishes_if_emeritus_leaves_battlefield(self) -> None:
        from engine.game import destroy

        game, p1, p2, emeritus, copy = self._prepared_setup()
        destroy(game, emeritus)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)  # resolve the leaves-battlefield trigger
        assert not game.get_exile(p1).contains(copy)
        assert not emeritus.prepared


class TestStandaloneSwords:
    def test_swords_helper_works_as_plain_instant(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[SwordsToPlowshares()], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Swords to Plowshares", targets=[bear])
        assert game.get_exile(p2).contains(bear)
        assert p2.life == 22
