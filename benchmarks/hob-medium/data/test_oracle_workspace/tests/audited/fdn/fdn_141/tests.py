"""Reference tests for FDN 141 — Giada, Font of Hope.

"Each other Angel you control enters with an additional +1/+1 counter on it for
each Angel you already control." This is a third-party enters-with-counters
*replacement* (rule 614.1c): as another Angel you control enters, Giada adds
one +1/+1 counter for each Angel you already control, on it *as* it enters.
"""

from __future__ import annotations

from cards.fdn.fdn_141.card_impl import GiadaFontOfHope
from engine.card import Creature
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _angel(p, name):
    return Creature(name=name, subtypes={"Angel"}, base_power=1,
                    base_toughness=1, owner=p, controller=p)


class TestGiadaProperties:
    def test_name_and_cost(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert card.name == "Giada, Font of Hope"
        assert card.mana_cost == ManaCost.parse("{1}{W}")


class TestGiadaThirdPartyEntryCounters:
    def test_entering_angel_gets_counter_per_existing_angel(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giada = GiadaFontOfHope(owner=p1, controller=p1)
        other = _angel(p1, "Serra Angel")
        set_board_state(game, 0, battlefield=[giada, other])
        giada.register_replacement_effects(game)

        # Two Angels already controlled (Giada + Serra) => +2 on the newcomer.
        newcomer = _angel(p1, "Youthful Valkyrie")
        set_board_state(game, 0, hand=[newcomer], battlefield=[giada, other])
        # (re-registering effects would double-count; keep the single Giada reg)
        move_to_zone(game, newcomer, Zone.HAND, Zone.BATTLEFIELD)
        assert newcomer.plus_one_counters == 2
        assert newcomer.power == 3
        assert newcomer.toughness == 3

    def test_giada_does_not_buff_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giada = GiadaFontOfHope(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[giada])
        # Entering Giada registers its replacement AFTER placement, so it never
        # buffs itself, and no other Angel is out.
        move_to_zone(game, giada, Zone.HAND, Zone.BATTLEFIELD)
        assert giada.plus_one_counters == 0

    def test_non_angel_gets_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giada = GiadaFontOfHope(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[giada])
        giada.register_replacement_effects(game)
        bear = Creature(name="Bear", subtypes={"Bear"}, base_power=2,
                        base_toughness=2, owner=p1, controller=p1)
        set_board_state(game, 0, hand=[bear], battlefield=[giada])
        move_to_zone(game, bear, Zone.HAND, Zone.BATTLEFIELD)
        assert bear.plus_one_counters == 0

    def test_opponent_angel_gets_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        giada = GiadaFontOfHope(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[giada])
        giada.register_replacement_effects(game)
        enemy_angel = _angel(p2, "Enemy Angel")
        set_board_state(game, 1, hand=[enemy_angel])
        move_to_zone(game, enemy_angel, Zone.HAND, Zone.BATTLEFIELD)
        # "Each other Angel *you* control" — the opponent's Angel is untouched.
        assert enemy_angel.plus_one_counters == 0
