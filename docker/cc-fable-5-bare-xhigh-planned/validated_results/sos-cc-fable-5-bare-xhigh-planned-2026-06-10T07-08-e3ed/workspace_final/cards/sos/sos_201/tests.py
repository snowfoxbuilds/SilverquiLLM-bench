"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature
from engine.game import draw_card
from engine.stack import priority_loop
from engine.turn import run_turn
from engine.types import Keyword, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _lorehold_on_battlefield(game, player_index=0):
    """Put Lorehold onto the battlefield through the real zone pipeline."""
    card = LoreholdTheHistorian()
    player = game.players[player_index]
    card.owner = card.controller = player
    player.zones[Zone.HAND].add(card)
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
    return card


class TestStatics:
    def test_card_data(self):
        card = LoreholdTheHistorian()
        assert card.name == "Lorehold, the Historian"
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5 and card.base_toughness == 5


class TestMiracle:
    def test_first_drawn_instant_cast_for_two(self):
        game = create_game()
        p1, p2 = game.players
        _lorehold_on_battlefield(game)
        bolt = BurstLightning()
        bolt.owner = bolt.controller = p1
        p1.zones[Zone.LIBRARY].add(bolt)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        draw_card(game, p1)
        # Resolve the miracle trigger: yes, target p2, then the bolt.
        p1._script.extend(["pass", True, p2, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p2.life == 18
        assert p1.zones[Zone.GRAVEYARD].contains(bolt)
        assert p1.mana_pool.total() == 0

    def test_not_first_draw_no_miracle(self):
        game = create_game()
        p1, p2 = game.players
        _lorehold_on_battlefield(game)
        bolt = BurstLightning()
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        for c in (bolt, filler):
            c.owner = c.controller = p1
        p1.zones[Zone.LIBRARY].add(bolt)     # second from top
        p1.zones[Zone.LIBRARY].add(filler)   # top
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        draw_card(game, p1)  # filler: a creature, no miracle
        assert game.stack.is_empty()
        draw_card(game, p1)  # bolt: not the first draw this turn
        assert game.stack.is_empty()
        assert p1.zones[Zone.HAND].contains(bolt)

    def test_decline_miracle_keeps_card_in_hand(self):
        game = create_game()
        p1, p2 = game.players
        _lorehold_on_battlefield(game)
        bolt = BurstLightning()
        bolt.owner = bolt.controller = p1
        p1.zones[Zone.LIBRARY].add(bolt)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        draw_card(game, p1)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert p1.zones[Zone.HAND].contains(bolt)
        assert p1.mana_pool.total() == 2

    def test_first_draw_resets_each_turn(self):
        game = create_game()
        p1, p2 = game.players
        _lorehold_on_battlefield(game)
        bolt = BurstLightning()
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        for c in (bolt, filler):
            c.owner = c.controller = p1
        p1.zones[Zone.LIBRARY].add(bolt)     # drawn next turn, first
        p1.zones[Zone.LIBRARY].add(filler)   # drawn this turn

        draw_card(game, p1)
        assert game.stack.is_empty()

        # Wrap to the next turn: the per-turn draw counter resets.
        from test_utils import advance_to_phase
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p1)
        assert not game.stack.is_empty()  # miracle trigger is waiting
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.zones[Zone.HAND].contains(bolt)


class TestUpkeepLoot:
    def _setup_p2_turn(self):
        game = create_game()
        p1, p2 = game.players
        _lorehold_on_battlefield(game, 0)
        keeper = Creature(name="Keeper", base_power=1, base_toughness=1)
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        drawn = Creature(name="Drawn", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[keeper, fodder])
        drawn.owner = drawn.controller = p1
        p1.zones[Zone.LIBRARY].add(drawn)
        for i in range(2):
            c = Creature(name=f"P2Lib{i}", base_power=1, base_toughness=1)
            c.owner = c.controller = p2
            p2.zones[Zone.LIBRARY].add(c)
        # Hand p2 the turn that is about to run.
        game.active_player_index = 1
        game.priority_player_index = 1
        game._normal_next_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        return game, p1, p2, keeper, fodder, drawn

    def test_discard_to_draw_at_opponent_upkeep(self):
        game, p1, p2, keeper, fodder, drawn = self._setup_p2_turn()
        p2._script.extend(["pass"])
        p1._script.extend(["pass", fodder])
        run_turn(game)

        assert p1.zones[Zone.GRAVEYARD].contains(fodder)
        assert p1.zones[Zone.HAND].contains(drawn)
        assert p1.zones[Zone.HAND].contains(keeper)

    def test_decline_loot(self):
        game, p1, p2, keeper, fodder, drawn = self._setup_p2_turn()
        p2._script.extend(["pass"])
        p1._script.extend(["pass", None])
        run_turn(game)

        assert p1.zones[Zone.HAND].contains(fodder)
        assert p1.zones[Zone.LIBRARY].contains(drawn)

    def test_no_loot_on_own_upkeep(self):
        game = create_game()
        p1, p2 = game.players
        _lorehold_on_battlefield(game, 0)
        card = Creature(name="HandCard", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[card])
        for i in range(2):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
            c.owner = c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)

        p1._script.append([])  # declare no attackers in combat
        run_turn(game)  # p1's own turn: upkeep trigger must not fire

        assert p1.zones[Zone.HAND].contains(card)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
