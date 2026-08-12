"""Reference tests for FDN 87 — Goblin Boarders.

Raid — "This creature enters with a +1/+1 counter on it if you attacked this
turn." The Raid condition is read from game state as the creature enters (rule
614.1c), so the counter is on it *as* it enters when the controller attacked
this turn — and no counter is added when they did not.
"""

from __future__ import annotations

from cards.fdn.fdn_87.card_impl import GoblinBoarders
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


class TestGoblinBoardersProperties:
    def test_name_and_cost(self) -> None:
        card = GoblinBoarders(owner=None)
        assert card.name == "Goblin Boarders"
        assert card.mana_cost == ManaCost.parse("{2}{R}")
        assert card.base_power == 3
        assert card.base_toughness == 2


class TestGoblinBoardersRaid:
    def test_enters_buffed_when_attacked_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.attacked_this_turn = True
        card = GoblinBoarders(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 1
        assert card.power == 4
        assert card.toughness == 3

    def test_enters_plain_when_not_attacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # No attack this turn (and the player carries no attacked flag).
        card = GoblinBoarders(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 0
        assert card.power == 3
        assert card.toughness == 2

    def test_reads_controller_attacked_flag(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p1.attacked_this_turn = True
        card = GoblinBoarders(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 1
