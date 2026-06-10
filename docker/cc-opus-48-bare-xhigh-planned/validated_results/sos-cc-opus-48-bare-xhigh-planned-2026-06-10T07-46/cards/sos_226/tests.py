"""Tests for SOS 226 — Silverquill, the Disputant (casualty 1, uses E1)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state, cast_spell


class _LifeGainInstant(Instant):
    """No-target probe instant: controller gains 4 life on resolve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gain4")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 4


def _silverquill_on_bf(game) -> SilverquillTheDisputant:
    p0 = game.players[0]
    sq = SilverquillTheDisputant(owner=p0, controller=p0)
    set_board_state(game, 0, hand=[sq])
    move_to_zone(game, sq, Zone.HAND, Zone.BATTLEFIELD)
    return sq


class TestProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4 and card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestCasualty:
    def test_sacrifice_copies_the_spell(self) -> None:
        game = create_game()
        p0 = game.players[0]
        sq = _silverquill_on_bf(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        probe = _LifeGainInstant(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[sq, bear], hand=[probe],
                        mana={ManaType.COLORLESS: 1})
        # Script the casualty sacrifice choice → the bear.
        p0._script.append(bear)
        before = p0.life
        cast_spell(game, 0, "Gain4")
        # Original + copy both resolved → +8 life.
        assert p0.life == before + 8
        # The bear was sacrificed.
        assert game.get_graveyard(p0).contains(bear)
        assert not game.get_battlefield(p0).contains(bear)
        assert game.get_graveyard(p0).contains(probe)

    def test_decline_no_copy(self) -> None:
        game = create_game()
        p0 = game.players[0]
        sq = _silverquill_on_bf(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        probe = _LifeGainInstant(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[sq, bear], hand=[probe],
                        mana={ManaType.COLORLESS: 1})
        # Decline the casualty by choosing None.
        p0._script.append(None)
        before = p0.life
        cast_spell(game, 0, "Gain4")
        assert p0.life == before + 4  # only the original
        assert game.get_battlefield(p0).contains(bear)  # not sacrificed

    def test_no_silverquill_no_casualty(self) -> None:
        """Without Silverquill on the battlefield, no casualty is granted."""
        game = create_game()
        p0 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        probe = _LifeGainInstant(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[bear], hand=[probe],
                        mana={ManaType.COLORLESS: 1})
        before = p0.life
        cast_spell(game, 0, "Gain4")
        assert p0.life == before + 4  # only the original, no copy
        assert game.get_battlefield(p0).contains(bear)  # nothing sacrificed


class TestCopyNotRecast:
    def test_copy_does_not_retrigger_casualty(self) -> None:
        """The copy is not 'cast' (E1 not re-fired), so casualty fires once."""
        game = create_game()
        p0 = game.players[0]
        sq = _silverquill_on_bf(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear2", base_power=2, base_toughness=2)
        probe = _LifeGainInstant(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[sq, bear, bear2], hand=[probe],
                        mana={ManaType.COLORLESS: 1})
        # Only one casualty decision should be requested.
        p0._script.append(bear)
        before = p0.life
        cast_spell(game, 0, "Gain4")
        # +8 (original + one copy). Only one bear sacrificed.
        assert p0.life == before + 8
        sacrificed = [c for c in [bear, bear2] if game.get_graveyard(p0).contains(c)]
        assert len(sacrificed) == 1
