"""Seeker's Folly's modes are chosen like any other choice, and each changes
only what its caster's opponent has."""

from __future__ import annotations

from cards.fdn.fdn_69.card_impl import SeekersFolly, SeekersFollyAbility2, SeekersFollyAbility3
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.card import printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Zone, card, create_game, player

from table import Table, moves

_MANA = {ManaType.BLACK: 1, ManaType.COLORLESS: 2}


class TestSeekersFollyProperties:
    def test_static_data(self):
        card = SeekersFolly(owner=None)
        assert printed_class(card) is SeekersFolly
        assert card.mana_cost == ManaCost.parse("{2}{B}")


class TestSeekersFollyModes:
    def test_mode0_targets_an_opponent_who_discards_two(self):
        folly = card(SeekersFolly)
        h1, h2, h3 = card(SavannahLions), card(LlanowarElves), card(BrazenScourge)
        game = create_game(
            Side(hand=[folly], mana=_MANA),
            Side(hand=[h1, h2, h3]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, folly, choices=[SeekersFollyAbility2, player(1)], then=[moves(folly, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, choices=[h1, h2], then=[
            moves(folly, Zone.GRAVEYARD), moves(h1, Zone.GRAVEYARD), moves(h2, Zone.GRAVEYARD),
        ], note="player 1 discards the two cards they choose")
        t.run()

    def test_mode1_shrinks_opponents_creatures(self):
        """-1/-1 kills the opponent's 1/1 and leaves its caster's 1/1 alive."""
        folly, mine, theirs = card(SeekersFolly), card(LlanowarElves), card(LlanowarElves)
        game = create_game(
            Side(hand=[folly], battlefield=[mine], mana=_MANA),
            Side(battlefield=[theirs]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, folly, choices=[SeekersFollyAbility3], then=[moves(folly, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(folly, Zone.GRAVEYARD), moves(theirs, Zone.GRAVEYARD)],
                note="only the opponent's creature gets -1/-1")
        t.run()

    def test_discard_mode_cannot_target_the_caster_or_a_creature(self):
        """Player 0 prefers to target themselves, then the opponent's creature,
        then the opponent: neither of the first two is a legal target, each
        either not offered or offered and rejected."""
        folly = card(SeekersFolly)
        mine = [card(SavannahLions), card(LlanowarElves)]
        h1, h2, h3 = card(SavannahLions), card(LlanowarElves), card(BrazenScourge)
        creature = card(BrazenScourge)
        game = create_game(
            Side(hand=[folly, *mine], mana=_MANA),
            Side(hand=[h1, h2, h3], battlefield=[creature]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, branches=[
            [folly, SeekersFollyAbility2, player(0), creature, player(1)],
            [folly, SeekersFollyAbility2, creature, player(1)],
            [folly, SeekersFollyAbility2, player(1)],
        ], then=[moves(folly, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, choices=[h1, h2], then=[
            moves(folly, Zone.GRAVEYARD), moves(h1, Zone.GRAVEYARD), moves(h2, Zone.GRAVEYARD),
        ], note="the opponent discards; the caster's hand and the creature stay")
        t.run()
