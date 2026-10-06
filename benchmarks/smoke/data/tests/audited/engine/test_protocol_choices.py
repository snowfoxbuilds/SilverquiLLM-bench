"""Phase 2 protocol tests for the non-targeting converted call sites:
damage-division query (combat damage), discard query (cleanup), and the
legend-rule OBJECT query.

The damage-division and discard tests play on the Test Interface: the
choices come from the players' scripts and show in what happens.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_171.card_impl import DiregrafGhoul
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import Decision, Side, Step, card, create_game

from engine.card import Creature
from engine.game_state import GameState
from engine.player import Player
from engine.queries import Answer
from engine.types import ManaCost, Supertype, Zone
from silverquillm.table import Table, moves, taps


class FnPlayer(Player):
    """Answers via an optional callback; defaults to the first ``min`` options."""

    def __init__(self, name: str, fn=None):
        super().__init__(name)
        self.fn = fn
        self.transcript: list = []

    def answer(self, query) -> Answer:
        self.transcript.append(query)
        if self.fn is not None:
            result = self.fn(query)
            if result is not None:
                return result
        return Answer(selected=tuple(query.options[: query.min]))


def _creature(name, *, legendary=False):
    supertypes = {Supertype.LEGENDARY} if legendary else set()
    return Creature(name=name, mana_cost=ManaCost(generic=1),
                    base_power=2, base_toughness=2, supertypes=supertypes)


def _put(game, player, zone, card):
    card.owner = player
    card.controller = player
    player.zones[zone].add(card)


class TestDamageDivisionQuery:
    def test_damage_division_query_applies_the_chosen_share(self):
        """Player 0 divides its Brazen Scourge's 3 damage all to the Diregraf
        Ghoul, so the Savannah Lions also blocking it survives."""
        scourge, lions, ghoul = card(BrazenScourge), card(SavannahLions), card(DiregrafGhoul)
        t = Table(create_game(Side(battlefield=[scourge]), Side(battlefield=[lions, ghoul]),
                              start=(Step.BEGIN_COMBAT, 0)))
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, scourge, then=[taps(scourge)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, lions, ghoul, scoped={lions: scourge, ghoul: scourge})
        t.pass_(0, per_query={ghoul: [Decision.number(3)], lions: [Decision.number(0)]})
        t.pass_(1, then=[moves(scourge, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)])
        t.run()


class TestDiscardQuery:
    def test_cleanup_discard_raises_object_queries_until_hand_size(self):
        """Player 0 ends their turn with nine cards in hand and discards the
        two they choose, down to seven (rule 514.1)."""
        hand = [card(Plains) for _ in range(9)]
        t = Table(create_game(Side(hand=hand), Side(library=[Plains]), start=(Step.END, 0)))
        t.pass_(0, choices=hand[:2])
        t.pass_(1, then=[moves(hand[0], Zone.GRAVEYARD), moves(hand[1], Zone.GRAVEYARD)])
        t.run()


class TestLegendRuleQuery:
    def test_legend_rule_keeps_chosen_object(self):
        from engine.state_based_actions import resolve_state_based_actions

        p0 = FnPlayer("P0")
        p1 = FnPlayer("P1")
        game = GameState([p0, p1])
        a = _creature("Hero", legendary=True)
        b = _creature("Hero", legendary=True)
        _put(game, p0, Zone.BATTLEFIELD, a)
        _put(game, p0, Zone.BATTLEFIELD, b)

        resolve_state_based_actions(game)

        bf = list(p0.zones[Zone.BATTLEFIELD].get_all())
        gy = list(p0.zones[Zone.GRAVEYARD].get_all())
        assert len(bf) == 1
        assert len(gy) == 1
        assert {id(x) for x in bf + gy} == {id(a), id(b)}
