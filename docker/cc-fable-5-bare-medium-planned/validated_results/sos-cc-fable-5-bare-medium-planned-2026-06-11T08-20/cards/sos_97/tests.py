"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

import random

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability, AbilityError
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _activate_loyalty(game, pw, index, targets=None):
    """Activate a loyalty ability by printed index through the engine."""
    controller = pw.controller
    game.active_player_index = game.players.index(controller)
    game.priority_player_index = game.active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    ability = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw, controller=controller,
        loyalty_cost=ability.loyalty_cost, effect=ability.effect,
    )
    activate_ability(game, controller, inst)
    if targets is not None:
        pw.chosen_targets = targets
    # Resolve through the priority loop.  The priority "pass" must be
    # consumed before any resolution prompts, so put it at the front.
    for p in game.players:
        p._script.appendleft("pass")
    priority_loop(game)


def _ral_on_battlefield(game, player_index=0):
    pw = RalZarekGuestLecturer()
    set_board_state(game, player_index, battlefield=[pw])
    return pw


class TestRalZarekGuestLecturer:
    def test_starting_loyalty(self):
        pw = RalZarekGuestLecturer()
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3

    def test_plus1_surveil_two(self):
        game = create_game()
        p0 = game.players[0]
        pw = _ral_on_battlefield(game)
        keep = Creature(name="Keep", base_power=1, base_toughness=1)
        binned = Instant(name="Binned", mana_cost=ManaCost.parse("{1}"))
        lib = p0.zones[Zone.LIBRARY]
        for c in (keep, binned):  # binned on top
            c.owner = c.controller = p0
            lib.add(c)
        # top card first: bin "Binned", keep "Keep"
        p0._script.extend([True, False])
        _activate_loyalty(game, pw, 0)
        assert pw.loyalty == 4
        assert game.get_graveyard(p0).contains(binned)
        assert lib.top(1)[0] is keep

    def test_minus1_targeted_players_discard(self):
        game = create_game()
        p0, p1 = game.players
        pw = _ral_on_battlefield(game)
        my_card = Instant(name="Mine", mana_cost=ManaCost.parse("{1}"))
        opp_card = Instant(name="Theirs", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[my_card], battlefield=[pw])
        set_board_state(game, 1, hand=[opp_card])
        p0._script.append(my_card)   # p0 chooses its discard
        p1._script.append(opp_card)  # p1 chooses its discard
        _activate_loyalty(game, pw, 1, targets=[p0, p1])
        assert pw.loyalty == 2
        assert game.get_graveyard(p0).contains(my_card)
        assert game.get_graveyard(p1).contains(opp_card)

    def test_minus1_zero_targets(self):
        game = create_game()
        pw = _ral_on_battlefield(game)
        _activate_loyalty(game, pw, 1, targets=[])
        assert pw.loyalty == 2

    def test_minus2_reanimates_small_creature(self):
        game = create_game()
        p0 = game.players[0]
        pw = _ral_on_battlefield(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, battlefield=[pw], graveyard=[bear])
        _activate_loyalty(game, pw, 2, targets=[bear])
        assert pw.loyalty == 1
        assert game.get_battlefield(p0).contains(bear)
        assert not game.get_graveyard(p0).contains(bear)

    def test_minus2_rejects_mv_above_three(self):
        game = create_game()
        p0 = game.players[0]
        pw = _ral_on_battlefield(game)
        ogre = Creature(name="Ogre", base_power=4, base_toughness=4,
                        mana_cost=ManaCost.parse("{3}{R}"))
        set_board_state(game, 0, battlefield=[pw], graveyard=[ogre])
        _activate_loyalty(game, pw, 2, targets=[ogre])
        assert pw.loyalty == 1  # cost paid; effect fizzles on bad target
        assert game.get_graveyard(p0).contains(ogre)

    def test_minus7_requires_loyalty(self):
        game = create_game()
        pw = _ral_on_battlefield(game)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        ability = pw.get_loyalty_abilities()[3]
        inst = LoyaltyAbilityInstance(
            source=pw, controller=pw.controller,
            loyalty_cost=ability.loyalty_cost, effect=ability.effect,
        )
        try:
            activate_ability(game, pw.controller, inst)
            assert False, "loyalty 3 cannot pay -7"
        except AbilityError:
            pass

    def test_minus7_coin_flips_skip_turns(self):
        game = create_game()
        p0, p1 = game.players
        pw = _ral_on_battlefield(game)
        pw.loyalty = 8
        game.rng = random.Random(7)
        rng_probe = random.Random(7)
        expected_heads = sum(rng_probe.randint(0, 1) for _ in range(5))
        _activate_loyalty(game, pw, 3, targets=[p1])
        assert pw.loyalty == 1
        assert p1.skip_turns == expected_heads
        assert expected_heads > 0  # seed 7 gives at least one head

        # The opponent's next turns are actually skipped: every turn wrap
        # keeps p0 as the active player until the skips are consumed.
        def _advance_one_turn():
            cur = game.turn_number
            while game.turn_number == cur:
                game.advance_phase()

        for _ in range(expected_heads):
            _advance_one_turn()
            assert game.active_player is p0  # p1's turn was skipped
        _advance_one_turn()
        assert game.active_player is p1  # skips exhausted
