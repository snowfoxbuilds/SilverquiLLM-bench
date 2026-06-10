"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_full_dfc_name_constructs_bare(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_swords_helper(self) -> None:
        s = SwordsToPlowshares(owner=None)
        assert s.name == "Swords to Plowshares"
        assert s.mana_cost == ManaCost.parse("{W}")


class TestETB:
    def test_creates_inkling_token_for_target_player(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 0,
                        hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0,
                   "Emeritus of Truce // Swords to Plowshares", targets=[p0])
        inklings = [c for c in game.get_battlefield(p0).get_all()
                    if "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 1
        assert Keyword.FLYING in inklings[0].keywords
        assert inklings[0].base_power == 1 and inklings[0].base_toughness == 1

    def test_prepared_when_opponent_has_more(self) -> None:
        game = create_game()
        p0, p1 = game.players
        from engine.types import ManaType

        set_board_state(game, 1, battlefield=_bears(3))
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0,
                   "Emeritus of Truce // Swords to Plowshares", targets=[p0])
        # You: Inkling + Emeritus = 2; opponent: 3 → prepared.
        assert emeritus.is_prepared is True

    def test_not_prepared_when_you_have_more(self) -> None:
        game = create_game()
        p0, p1 = game.players
        from engine.types import ManaType

        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0,
                   "Emeritus of Truce // Swords to Plowshares", targets=[p0])
        assert emeritus.is_prepared is False


class TestPreparedSpell:
    def test_prepare_creates_copy_then_cast_pays_and_exiles(self) -> None:
        # Full flow: cast Emeritus with an opponent ahead on creatures so it
        # becomes prepared (copy created in exile), then cast that copy paying
        # {W}, exiling a creature and granting its controller life = power.
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0,
                   "Emeritus of Truce // Swords to Plowshares", targets=[p0])
        assert emeritus.is_prepared is True
        copies = [c for c in game.get_exile(p0).get_all()
                  if c.name == "Swords to Plowshares"]
        assert len(copies) == 1  # created in exile on becoming prepared

        victim = next(c for c in game.get_battlefield(p1).get_all()
                      if c.name.startswith("Bear"))
        set_board_state(game, 0, mana={ManaType.WHITE: 1})  # pay {W}
        p0._script.appendleft(victim)  # Swords' target
        emeritus.cast_prepared_spell(game)
        _resolve_all(game)

        assert game.get_exile(p1).contains(victim)  # exiled
        assert p1.life == 22  # victim's controller gains 2 (its power)
        assert emeritus.is_prepared is False  # unprepared as it became cast
        assert p0.mana_pool.get(ManaType.WHITE) == 0  # {W} was paid

    def test_cannot_cast_without_mana(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0,
                   "Emeritus of Truce // Swords to Plowshares", targets=[p0])
        assert emeritus.is_prepared is True
        # No mana available → cannot cast the copy; stays prepared.
        emeritus.cast_prepared_spell(game)
        assert game.stack.is_empty()
        assert emeritus.is_prepared is True

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        emeritus.is_prepared = False
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.cast_prepared_spell(game)
        assert game.stack.is_empty()  # nothing cast
