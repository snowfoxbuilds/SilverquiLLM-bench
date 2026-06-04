"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Planeswalker, Sorcery
from engine.game_state import _TURN_SEQUENCE
from engine.types import ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state, _resolve_top_of_stack


def _sorcery(name="Spell", cost="{1}{U}"):
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _activate_loyalty(game, player, pw, index):
    clear_loyalty_tracking()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    ability = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw,
        controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        description=ability.description,
    )
    activate_ability(game, player, inst)
    _resolve_top_of_stack(game)


def _set_library(game, player, cards):
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in cards:  # given bottom-to-top
        c.owner = player
        c.controller = player
        lib.add(c)


def _advance_one_turn(game):
    for _ in range(len(_TURN_SEQUENCE)):
        game.advance_phase()


class TestProperties:
    def test_is_planeswalker(self):
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_name(self):
        assert (
            RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"
        )

    def test_mana_cost(self):
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self):
        assert RalZarekGuestLecturer(owner=None).loyalty == 3

    def test_legendary(self):
        assert Supertype.LEGENDARY in RalZarekGuestLecturer(owner=None).supertypes

    def test_has_four_loyalty_abilities(self):
        assert len(RalZarekGuestLecturer(owner=None).get_loyalty_abilities()) == 4


class TestPlusOneSurveil:
    def test_surveils_two_cards(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[pw])
        top = _sorcery("TopCard")
        buried = _sorcery("BuriedCard")
        _set_library(game, p0, [buried, top])  # buried bottom, top on top
        p0._script.append("graveyard")  # decision for top card
        p0._script.append("top")  # decision for buried card
        _activate_loyalty(game, p0, pw, 0)
        assert top in p0.zones[Zone.GRAVEYARD].get_all()
        assert buried not in p0.zones[Zone.GRAVEYARD].get_all()
        assert pw.loyalty == 4

    def test_keeps_card_on_top(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[pw])
        top = _sorcery("TopCard")
        buried = _sorcery("BuriedCard")
        _set_library(game, p0, [buried, top])
        p0._script.append("top")
        p0._script.append("top")
        _activate_loyalty(game, p0, pw, 0)
        assert len(p0.zones[Zone.LIBRARY]) == 2
        assert len(p0.zones[Zone.GRAVEYARD]) == 0


class TestMinusOneDiscard:
    def test_target_player_discards(self):
        game = create_game()
        p0, p1 = game.players
        pw = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[pw])
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, hand=[bear])
        pw._resolve_targets = [p1]
        p1._script.append(bear)
        _activate_loyalty(game, p0, pw, 1)
        assert bear in p1.zones[Zone.GRAVEYARD].get_all()
        assert pw.loyalty == 2

    def test_no_targets_no_discard(self):
        game = create_game()
        p0, p1 = game.players
        pw = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[pw])
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, hand=[bear])
        pw._resolve_targets = []
        _activate_loyalty(game, p0, pw, 1)
        assert bear in p1.zones[Zone.HAND].get_all()


class TestMinusTwoReanimate:
    def test_returns_small_creature(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=None)
        bear = Creature(
            name="Bear",
            base_power=2,
            base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"),
        )
        set_board_state(game, 0, battlefield=[pw], graveyard=[bear])
        pw._resolve_target = bear
        _activate_loyalty(game, p0, pw, 2)
        assert bear in p0.zones[Zone.BATTLEFIELD].get_all()
        assert bear not in p0.zones[Zone.GRAVEYARD].get_all()
        assert pw.loyalty == 1

    def test_rejects_high_mana_value(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=None)
        big = Creature(
            name="Big",
            base_power=6,
            base_toughness=6,
            mana_cost=ManaCost.parse("{4}{G}"),
        )
        set_board_state(game, 0, battlefield=[pw], graveyard=[big])
        pw._resolve_target = big
        _activate_loyalty(game, p0, pw, 2)
        assert big in p0.zones[Zone.GRAVEYARD].get_all()
        assert big not in p0.zones[Zone.BATTLEFIELD].get_all()

    def test_rejects_noncreature(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=None)
        spell = _sorcery("Bolt", "{R}")
        set_board_state(game, 0, battlefield=[pw], graveyard=[spell])
        pw._resolve_target = spell
        _activate_loyalty(game, p0, pw, 2)
        assert spell in p0.zones[Zone.GRAVEYARD].get_all()


class TestMinusSevenCoins:
    def test_heads_set_skip_turns(self):
        game = create_game()
        p0, p1 = game.players
        pw = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[pw])
        pw.loyalty = 7
        pw._resolve_target = p1
        for v in [True, True, False, True, False]:  # 3 heads
            p0._script.append(v)
        _activate_loyalty(game, p0, pw, 3)
        assert game.skip_turns[game.players.index(p1)] == 3
        assert pw.loyalty == 0

    def test_zero_heads_no_skip(self):
        game = create_game()
        p0, p1 = game.players
        pw = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[pw])
        pw.loyalty = 7
        pw._resolve_target = p1
        for _ in range(5):
            p0._script.append(False)
        _activate_loyalty(game, p0, pw, 3)
        assert game.skip_turns.get(game.players.index(p1), 0) == 0


class TestSkipTurnsRotation:
    def test_skip_passes_turn_back(self):
        game = create_game()
        game.active_player_index = 0
        game._normal_next_index = 1
        game.skip_turns[1] = 1
        _advance_one_turn(game)
        assert game.active_player_index == 0
        assert game.skip_turns[1] == 0

    def test_normal_rotation_without_skip(self):
        game = create_game()
        game.active_player_index = 0
        game._normal_next_index = 1
        _advance_one_turn(game)
        assert game.active_player_index == 1
