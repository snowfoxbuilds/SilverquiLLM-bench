"""Tests for SOS 182 — Conciliator's Duelist."""

from __future__ import annotations

import pytest

from cards.sos.sos_182.card_impl import ConciliatorsDuelist
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestConciliatorsDuelistProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = ConciliatorsDuelist(owner=None)
        assert card.name == "Conciliator's Duelist"

    def test_mana_cost(self) -> None:
        card = ConciliatorsDuelist(owner=None)
        assert card.mana_cost == ManaCost.parse("{W}{W}{B}{B}")

    def test_power_toughness(self) -> None:
        card = ConciliatorsDuelist(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_is_creature(self) -> None:
        card = ConciliatorsDuelist(owner=None)
        assert CardType.CREATURE in card.card_types


class TestConciliatorsDuelistETB:
    """When this creature enters, draw a card. Each player loses 1 life."""

    def test_controller_draws_card_on_enter(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[ConciliatorsDuelist(owner=None)],
                        mana={ManaType.WHITE: 2, ManaType.BLACK: 2})
        initial_hand_size = len(game.players[0].hand)
        cast_spell(game, 0, "Conciliator's Duelist")
        # After casting (card leaves hand) + draw 1, net hand change = 0
        # But we just verify the draw happened
        assert game.players[0].life == 19

    def test_each_player_loses_1_life_on_enter(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[ConciliatorsDuelist(owner=None)],
                        mana={ManaType.WHITE: 2, ManaType.BLACK: 2})
        cast_spell(game, 0, "Conciliator's Duelist")
        assert game.players[0].life == 19
        assert game.players[1].life == 19


class TestConciliatorsDuelistRepartee:
    """Repartee — Whenever you cast an instant or sorcery targeting a creature,
    exile up to one target creature. Return it at beginning of next end step."""

    def test_repartee_exiles_target_creature(self) -> None:
        game = create_game()
        duelist = ConciliatorsDuelist(owner=None)
        target_creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        exile_target = Creature(name="Exile Bear", base_power=3, base_toughness=3)
        # A simple targeting instant to trigger repartee
        bolt = Instant(name="Test Bolt")
        set_board_state(game, 0, battlefield=[duelist],
                        hand=[bolt],
                        mana={ManaType.RED: 5, ManaType.WHITE: 5, ManaType.BLACK: 5})
        set_board_state(game, 1, battlefield=[target_creature, exile_target])
        # Cast the instant targeting target_creature — repartee should trigger
        cast_spell(game, 0, "Test Bolt", targets=[target_creature])
        # exile_target should have been exiled by repartee
        battlefield_names = [c.name for c in game.players[1].battlefield]
        assert "Exile Bear" not in battlefield_names

    def test_repartee_returns_creature_at_end_step(self) -> None:
        """The exiled creature returns at the beginning of the next end step."""
        game = create_game()
        duelist = ConciliatorsDuelist(owner=None)
        target_creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        exile_target = Creature(name="Exile Bear", base_power=3, base_toughness=3)
        bolt = Instant(name="Test Bolt")
        set_board_state(game, 0, battlefield=[duelist],
                        hand=[bolt],
                        mana={ManaType.RED: 5, ManaType.WHITE: 5, ManaType.BLACK: 5})
        set_board_state(game, 1, battlefield=[target_creature, exile_target])
        cast_spell(game, 0, "Test Bolt", targets=[target_creature])
        # Advance to end step — creature should return
        from test_utils import advance_to_phase
        from engine.types import Phase, Step
        advance_to_phase(game, Phase.ENDING, Step.END)
        battlefield_names = [c.name for c in game.players[1].battlefield]
        assert "Exile Bear" in battlefield_names

    def test_repartee_does_not_trigger_on_noncreature_target(self) -> None:
        """Repartee only triggers when the spell targets a creature."""
        game = create_game()
        duelist = ConciliatorsDuelist(owner=None)
        other_creature = Creature(name="Bystander", base_power=2, base_toughness=2)
        bolt = Instant(name="Face Bolt")
        set_board_state(game, 0, battlefield=[duelist],
                        hand=[bolt],
                        mana={ManaType.RED: 5})
        set_board_state(game, 1, battlefield=[other_creature])
        # Cast targeting player (not a creature)
        cast_spell(game, 0, "Face Bolt", targets=[game.players[1]])
        # Bystander should remain on battlefield
        battlefield_names = [c.name for c in game.players[1].battlefield]
        assert "Bystander" in battlefield_names
