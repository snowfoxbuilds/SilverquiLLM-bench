"""Tests for SOS 28 — Rapier Wit."""

from __future__ import annotations

import pytest
from cards.sos.sos_28.card_impl import RapierWit
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Zone, TargetRequirement
from test_utils import create_game, set_board_state, cast_spell, advance_to_phase


class TestRapierWitProperties:
    """Static card data should match the SOS 28 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(RapierWit(owner=None), Instant)

    def test_name(self) -> None:
        assert RapierWit(owner=None).name == "Rapier Wit"

    def test_mana_cost(self) -> None:
        assert RapierWit(owner=None).mana_cost == ManaCost.parse("{1}{W}")


class TestRapierWitTargeting:
    """Targets a creature."""

    def test_targets_single_creature(self) -> None:
        game = create_game()
        spell = RapierWit(owner=None)
        reqs = spell.get_targets(game)
        assert len(reqs) == 1
        req = reqs[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        spell = RapierWit(owner=None)
        req = spell.get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestRapierWitResolution:
    """Tap target creature. If it's your turn, put a stun counter on it. Draw a card."""

    def test_taps_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.is_tapped = False
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[RapierWit(owner=p1)], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        assert bear.is_tapped is True

    def test_stun_counter_on_own_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.is_tapped = False
        bear.stun_counters = 0
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[RapierWit(owner=p1)], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # Ensure it's player 0's turn
        game.active_player_index = 0
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        assert bear.stun_counters >= 1

    def test_no_stun_counter_on_opponents_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.is_tapped = False
        bear.stun_counters = 0
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[RapierWit(owner=p1)], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # Set active player to opponent
        game.active_player_index = 1
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        assert bear.stun_counters == 0

    def test_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.is_tapped = False
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[RapierWit(owner=p1)], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        hand_before = len(game.get_hand(p1))
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        # Hand should have +1 card (spell left hand but drew a card)
        # After casting, spell leaves hand (-1) but draw happens (+1), net 0 from original
        # But we also need to account for the spell being consumed
        hand_after = len(game.get_hand(p1))
        # Original hand had 1 card (the spell). After cast, spell goes to GY, draw 1 => hand = 1
        assert hand_after == hand_before  # net zero: -1 spell + 1 draw
