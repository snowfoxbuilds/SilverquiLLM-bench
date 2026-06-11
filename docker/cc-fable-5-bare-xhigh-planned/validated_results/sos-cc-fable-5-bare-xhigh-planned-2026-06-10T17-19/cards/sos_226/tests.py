"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _game_with_silverquill(extra_battlefield):
    """Cast Silverquill through the real pipeline so triggers register."""
    game = create_game()
    set_board_state(
        game, 0,
        hand=[SilverquillTheDisputant(owner=None)],
        battlefield=list(extra_battlefield),
        mana={ManaType.COLORLESS: 2, ManaType.WHITE: 1, ManaType.BLACK: 1},
    )
    cast_spell(game, 0, "Silverquill, the Disputant")
    return game


class TestSilverquillStatics:
    def test_card_data(self):
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4 and card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords


class TestSilverquillCasualty:
    def test_casualty_sacrifices_and_copies_spell(self):
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([fodder, bear])
        p1 = game.players[0]
        ff = FleetingFlight(owner=None)
        p1.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p1
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1._script.append(fodder)  # casualty sacrifice choice
        p1._script.append(False)   # keep same targets for the copy
        cast_spell(game, 0, "Fleeting Flight", targets=[bear])
        # Copy + original both resolved on the bear.
        assert bear.plus_one_counters == 2
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)

    def test_decline_casualty_no_copy(self):
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([fodder, bear])
        p1 = game.players[0]
        ff = FleetingFlight(owner=None)
        p1.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p1
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1._script.append(None)  # decline casualty
        cast_spell(game, 0, "Fleeting Flight", targets=[bear])
        assert bear.plus_one_counters == 1
        assert game.get_battlefield(p1).contains(fodder)

    def test_copy_may_choose_new_targets(self):
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        bear1 = Creature(name="Bear One", base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear Two", base_power=2, base_toughness=2)
        game = _game_with_silverquill([fodder, bear1, bear2])
        p1 = game.players[0]
        ff = FleetingFlight(owner=None)
        p1.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p1
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1._script.append(fodder)  # casualty sacrifice
        p1._script.append(True)    # choose new targets for the copy
        p1._script.append(bear2)   # the copy's new target
        cast_spell(game, 0, "Fleeting Flight", targets=[bear1])
        assert bear1.plus_one_counters == 1
        assert bear2.plus_one_counters == 1

    def test_power_zero_creature_cannot_be_casualty(self):
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([wall, bear])
        p1 = game.players[0]
        ff = FleetingFlight(owner=None)
        p1.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p1
        p1.mana_pool.add(ManaType.WHITE, 1)
        # Candidates exclude the 0-power wall; decline sacrificing the rest.
        p1._script.append(None)
        cast_spell(game, 0, "Fleeting Flight", targets=[bear])
        assert bear.plus_one_counters == 1
        assert game.get_battlefield(p1).contains(wall)

    def test_opponent_spells_do_not_get_casualty(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([bear])
        p2 = game.players[1]
        ff = FleetingFlight(owner=None)
        p2.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p2
        p2.mana_pool.add(ManaType.WHITE, 1)
        fodder2 = Creature(name="Opp Fodder", base_power=1, base_toughness=1)
        set_board_state(game, 1, battlefield=[fodder2])
        # No casualty prompt for the opponent — no scripted answers needed.
        cast_spell(game, 1, "Fleeting Flight", targets=[bear])
        assert bear.plus_one_counters == 1
        assert game.get_battlefield(p2).contains(fodder2)
