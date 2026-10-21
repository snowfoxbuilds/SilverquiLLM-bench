"""Audited tests for FDN 17 — Herald of Eternal Dawn.

"You can't lose the game and your opponents can't win the game." A player at
0 life or who drew from an empty library would lose the game (rules 704.5a and
704.5b), but the "can't" wins (rule 101.2): the game goes on for as long as
Herald stays on the battlefield. A draw from an empty library counts only at
the next state-based action check, so one made while Herald was there never
costs the game once it leaves.
"""

from __future__ import annotations

from cards.fdn.fdn_17.card_impl import HeraldOfEternalDawn
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_192.card_impl import BurstLightning
from test_interface import ManaType, Phase, Side, Zone, card, create_game, player

from table import Table, life, moves, wins

MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _burn_to_zero(herald, *, seat1_hand=(), seat1_mana=None):
    """Player 0, at 2 life with Herald, takes 2 from player 1's Burst Lightning."""
    bolt = card(BurstLightning)
    game = create_game(
        Side(battlefield=[herald], life=2),
        Side(hand=[bolt, *seat1_hand], mana={ManaType.RED: 1, **(seat1_mana or {})}),
        start=MAIN,
    )
    t = Table(game)
    t.pass_(0)
    t.act(1, bolt, choices=[player(0)], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), life(0, 0)])
    return t


def _draw_from_empty_library(herald, think, *, seat1_hand=(), seat1_mana=None):
    """Player 0, with Herald and an empty library, draws nothing with Think Twice."""
    game = create_game(
        Side(battlefield=[herald], mana={ManaType.BLUE: 5}, hand=[think]),
        Side(hand=list(seat1_hand), mana=seat1_mana or {}),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, think, then=[moves(think, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(think, Zone.GRAVEYARD)])
    return t


class TestHeraldOfEternalDawnCantLose:
    def test_its_controller_at_zero_life_does_not_lose(self) -> None:
        """At 0 life with Herald, player 0 plays on to the end of the turn."""
        t = _burn_to_zero(card(HeraldOfEternalDawn))
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.run()

    def test_its_controller_loses_once_it_leaves(self) -> None:
        """Destroying Herald while player 0 is at 0 life ends the game."""
        herald, downfall = card(HeraldOfEternalDawn), card(HerosDownfall)
        t = _burn_to_zero(herald, seat1_hand=[downfall], seat1_mana={ManaType.BLACK: 3})
        t.pass_(0)
        t.act(1, downfall, choices=[herald], then=[moves(downfall, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(downfall, Zone.GRAVEYARD), moves(herald, Zone.GRAVEYARD), wins(1)])
        t.run()

    def test_its_controller_drawing_from_an_empty_library_does_not_lose(self) -> None:
        """Drawing from an empty library with Herald, player 0 plays on to the end of the turn."""
        t = _draw_from_empty_library(card(HeraldOfEternalDawn), card(ThinkTwice))
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.run()

    def test_a_draw_made_with_it_does_not_cost_the_game_once_it_leaves(self) -> None:
        """Destroying Herald after the empty-library draw leaves player 0 in the
        game; their next draw from it, Think Twice's flashback, loses it."""
        herald, think, downfall = card(HeraldOfEternalDawn), card(ThinkTwice), card(HerosDownfall)
        t = _draw_from_empty_library(herald, think, seat1_hand=[downfall], seat1_mana={ManaType.BLACK: 3})
        t.pass_(0)
        t.act(1, downfall, choices=[herald], then=[moves(downfall, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(downfall, Zone.GRAVEYARD), moves(herald, Zone.GRAVEYARD)])
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(think, Zone.EXILE), wins(1)])
        t.run()
