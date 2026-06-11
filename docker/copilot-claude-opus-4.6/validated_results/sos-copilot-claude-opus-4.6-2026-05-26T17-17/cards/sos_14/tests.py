"""Tests for SOS 14 — Ennis, Debate Moderator.

Legendary 1/1 Human Cleric for {1}{W}.
ETB: exile up to one other target creature you control. Return that card
at the beginning of the next end step.
At the beginning of your end step, if one or more cards were put into
exile this turn, put a +1/+1 counter on Ennis.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_14.card_impl import EnnisDebateModerator
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class TestEnnisProperties:
    """Static card data should match the SOS 14 spec."""

    def test_is_creature(self) -> None:
        card = EnnisDebateModerator(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert EnnisDebateModerator(owner=None).name == "Ennis, Debate Moderator"

    def test_mana_cost(self) -> None:
        assert EnnisDebateModerator(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = EnnisDebateModerator(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_is_legendary(self) -> None:
        card = EnnisDebateModerator(owner=None)
        assert Supertype.LEGENDARY in card.supertypes


class TestEnnisETBExile:
    """ETB: exile up to one other target creature you control."""

    def test_exiles_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ennis = EnnisDebateModerator(owner=p1, controller=p1)
        target = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p1).add(target)
        game.get_battlefield(p1).add(ennis)

        ennis.chosen_targets = [target]
        ennis.on_resolve(game)

        # Target should be in exile
        exile = game.get_exile(p1)
        exile_cards = exile.get_all()
        assert target in exile_cards

    def test_exiled_creature_leaves_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ennis = EnnisDebateModerator(owner=p1, controller=p1)
        target = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p1).add(target)
        game.get_battlefield(p1).add(ennis)

        ennis.chosen_targets = [target]
        ennis.on_resolve(game)

        bf = game.get_battlefield(p1)
        assert target not in bf.get_all()

    def test_up_to_one_allows_zero_targets(self) -> None:
        """With no target chosen, ETB should be a no-op (no crash)."""
        game = create_game()
        p1 = game.players[0]
        ennis = EnnisDebateModerator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ennis)

        ennis.chosen_targets = []
        # Should not raise
        ennis.on_resolve(game)


class TestEnnisEndStepCounter:
    """At your end step, if card(s) were exiled this turn, +1/+1 counter on Ennis."""

    def test_gets_counter_when_card_exiled_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ennis = EnnisDebateModerator(owner=p1, controller=p1)
        target = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p1).add(target)
        game.get_battlefield(p1).add(ennis)

        ennis.chosen_targets = [target]
        ennis.on_resolve(game)

        # Simulate end step trigger
        before_counters = ennis.plus_one_counters
        if hasattr(ennis, "end_step_trigger"):
            ennis.end_step_trigger(game)
        elif hasattr(ennis, "on_end_step"):
            ennis.on_end_step(game)
        else:
            # Trigger should exist - this assertion will fail in red phase
            assert hasattr(ennis, "end_step_trigger") or hasattr(ennis, "on_end_step"), \
                "Ennis needs an end step trigger method"
        assert ennis.plus_one_counters == before_counters + 1
