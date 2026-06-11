"""Tests for sos_97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, Planeswalker
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state, _resolve_top_of_stack


class TestRalProperties:
    def test_name(self) -> None:
        assert RalZarekGuestLecturer().name == "Ral Zarek, Guest Lecturer"

    def test_starting_loyalty(self) -> None:
        assert RalZarekGuestLecturer().loyalty == 3

    def test_is_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(), Planeswalker)

    def test_four_loyalty_abilities(self) -> None:
        assert len(RalZarekGuestLecturer().get_loyalty_abilities()) == 4


class TestSurveil:
    def test_plus1_puts_card_in_graveyard_when_chosen(self) -> None:
        """+1 surveil: player may put top cards into graveyard."""
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer()
        ral.controller = p0
        set_board_state(game, 0, battlefield=[ral])

        c1 = Instant(name="Card1", mana_cost=ManaCost(generic=0))
        c2 = Instant(name="Card2", mana_cost=ManaCost(generic=0))
        p0.zones[Zone.LIBRARY]._objects.clear()
        c1.owner = p0
        c2.owner = p0
        p0.zones[Zone.LIBRARY]._objects.extend([c1, c2])  # c2 is top

        # Script: yes (bin c2), no (keep c1)
        p0._script.extend([True, False])

        ability = ral.get_loyalty_abilities()[0]  # +1
        ability.effect(game)

        assert p0.zones[Zone.GRAVEYARD].contains(c2)
        assert not p0.zones[Zone.GRAVEYARD].contains(c1)

    def test_plus1_keeps_card_on_library_when_not_chosen(self) -> None:
        """+1 surveil: card stays on top when player declines."""
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer()
        ral.controller = p0

        card = Instant(name="Keep", mana_cost=ManaCost(generic=0))
        p0.zones[Zone.LIBRARY]._objects.clear()
        card.owner = p0
        p0.zones[Zone.LIBRARY]._objects.append(card)

        p0._script.append(False)  # keep it

        ability = ral.get_loyalty_abilities()[0]
        ability.effect(game)

        assert p0.zones[Zone.LIBRARY].top(1)[0] is card


class TestDiscard:
    def test_minus1_targets_discard(self) -> None:
        """−1: targeted players each discard a card."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        ral = RalZarekGuestLecturer()
        ral.controller = p0

        hand_card = Instant(name="Discard", mana_cost=ManaCost(generic=0))
        set_board_state(game, 1, hand=[hand_card])

        ral.chosen_targets = [p1]
        # p1 must choose which card to discard
        p1._script.append(hand_card)

        ability = ral.get_loyalty_abilities()[1]  # −1
        ability.effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(hand_card)
        assert not game.get_hand(p1).contains(hand_card)


class TestReanimate:
    def test_minus2_reanimates_creature_from_graveyard(self) -> None:
        """−2: Return target creature (MV ≤ 3) from graveyard to battlefield."""
        from engine.zones import move_to_zone

        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer()
        ral.controller = p0

        target = Creature(name="Bear", base_power=2, base_toughness=2,
                          mana_cost=ManaCost(generic=2))
        set_board_state(game, 0, graveyard=[target])

        ral.chosen_targets = [target]

        ability = ral.get_loyalty_abilities()[2]  # −2
        ability.effect(game)

        bf = game.get_battlefield(p0)
        assert bf.contains(target)
        assert not p0.zones[Zone.GRAVEYARD].contains(target)


class TestCoinFlipUltimate:
    def test_minus7_all_heads_skips_five_turns(self) -> None:
        """−7 with all heads: target opponent skips 5 turns."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        ral = RalZarekGuestLecturer()
        ral.controller = p0

        # Seed RNG so all flips are heads
        seeded_rng = random.Random()
        seeded_rng.seed(42)  # unknown outcome; override randint instead
        game.rng = seeded_rng

        # Monkeypatch to always return heads
        game.rng.randint = lambda a, b: 1  # always heads

        ral.chosen_targets = [p1]

        ability = ral.get_loyalty_abilities()[3]  # −7
        ability.effect(game)

        assert p1.skip_turns == 5

    def test_minus7_all_tails_no_turns_skipped(self) -> None:
        """−7 with all tails: opponent skips 0 turns."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        ral = RalZarekGuestLecturer()
        ral.controller = p0

        game.rng = random.Random()
        game.rng.randint = lambda a, b: 0  # always tails

        ral.chosen_targets = [p1]

        ability = ral.get_loyalty_abilities()[3]  # −7
        ability.effect(game)

        assert getattr(p1, "skip_turns", 0) == 0

    def test_skip_turns_causes_turn_to_be_skipped(self) -> None:
        """Player with skip_turns > 0 has their turn skipped in advance_phase."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]

        # Mark p1 to skip their next turn
        p1.skip_turns = 1
        game.active_player_index = 0  # p0's turn

        # Advance through all phases to end p0's turn
        from engine.game_state import _TURN_SEQUENCE
        for _ in range(len(_TURN_SEQUENCE)):
            game.advance_phase()

        # Should have wrapped to p0 again (p1's turn was skipped)
        assert game.active_player is p0
        # p1's skip_turns should have been decremented
        assert p1.skip_turns == 0
