"""Tests for SOS 80 — Emeritus of Woe // Demonic Tutor.

Emeritus of Woe is a 5/4 Black Vampire Warlock for {3}{B} that enters
prepared. While prepared, you may cast a copy of its spell side (Demonic
Tutor — search your library for a card, put it into your hand). Doing so
unprepares it.

At the beginning of your end step, if two or more creatures died this turn,
this creature becomes prepared again.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_80.card_impl import EmeritusOfWoeDemonicTutor
from engine.card import Creature
from engine.events import CreatureDiesTriggeredEvent, EndStepTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestEmeritusOfWoeProperties:
    """The creature face should have correct static characteristics."""

    def test_is_creature(self) -> None:
        card = EmeritusOfWoeDemonicTutor(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfWoeDemonicTutor(owner=None)
        assert card.name == "Emeritus of Woe"

    def test_mana_cost(self) -> None:
        card = EmeritusOfWoeDemonicTutor(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfWoeDemonicTutor(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 4

    def test_subtypes_include_vampire_warlock(self) -> None:
        card = EmeritusOfWoeDemonicTutor(owner=None)
        assert "Vampire" in card.subtypes
        assert "Warlock" in card.subtypes


# ---------------------------------------------------------------------------
# Enters prepared
# ---------------------------------------------------------------------------


class TestEmeritusEntersPrepared:
    """This creature enters the battlefield prepared."""

    def test_enters_prepared(self) -> None:
        """When Emeritus of Woe enters the battlefield, it should be prepared."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # After ETB, the card should be prepared
        assert card.is_prepared is True

    def test_is_prepared_after_on_enter(self) -> None:
        """Calling on_enter should set prepared state."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.on_enter(game)
        assert card.is_prepared is True


# ---------------------------------------------------------------------------
# Prepared spell — Demonic Tutor effect
# ---------------------------------------------------------------------------


class TestEmeritusPreparedSpell:
    """While prepared, casting the spell copy should work like Demonic Tutor."""

    def test_can_cast_prepared_spell_when_prepared(self) -> None:
        """Should be able to cast prepared spell when is_prepared is True."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = True
        set_board_state(game, 0, battlefield=[card])
        # Should not raise
        assert card.can_cast_prepared_spell(game) is True

    def test_cannot_cast_prepared_spell_when_not_prepared(self) -> None:
        """Should not be able to cast the spell if not prepared."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])
        assert card.can_cast_prepared_spell(game) is False

    def test_casting_prepared_spell_unprepares(self) -> None:
        """Casting the prepared spell should unprepare the creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = True
        set_board_state(game, 0, battlefield=[card])
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_demonic_tutor_searches_library(self) -> None:
        """Demonic Tutor: Search library for a card, put it into your hand."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = True
        # Put some cards in the library to search from
        target_card = Creature(name="Target Card", base_power=1, base_toughness=1)
        target_card.owner = p1
        set_board_state(game, 0, battlefield=[card])
        # Add card to library
        game.get_library(p1).add(target_card)
        hand_before = len(game.get_hand(p1).get_all())
        card.cast_prepared_spell(game)
        hand_after = len(game.get_hand(p1).get_all())
        # Should have one more card in hand (searched from library)
        assert hand_after == hand_before + 1

    def test_demonic_tutor_removes_from_library(self) -> None:
        """The searched card should be removed from library."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = True
        target_card = Creature(name="Target Card", base_power=2, base_toughness=2)
        target_card.owner = p1
        set_board_state(game, 0, battlefield=[card])
        game.get_library(p1).add(target_card)
        lib_before = len(game.get_library(p1).get_all())
        card.cast_prepared_spell(game)
        lib_after = len(game.get_library(p1).get_all())
        assert lib_after == lib_before - 1


# ---------------------------------------------------------------------------
# End step trigger — becomes prepared if 2+ creatures died
# ---------------------------------------------------------------------------


class TestEmeritusEndStepTrigger:
    """At beginning of end step, if 2+ creatures died this turn, becomes prepared."""

    def test_becomes_prepared_when_two_creatures_died(self) -> None:
        """If two creatures died this turn, Emeritus becomes prepared at end step."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])

        # Simulate two creatures dying this turn
        dead1 = Creature(name="Dead One", base_power=1, base_toughness=1)
        dead2 = Creature(name="Dead Two", base_power=2, base_toughness=2)
        game.record_creature_death(dead1)
        game.record_creature_death(dead2)

        # Fire end step trigger
        card.check_end_step_trigger(game)
        assert card.is_prepared is True

    def test_does_not_become_prepared_with_only_one_death(self) -> None:
        """If only one creature died, Emeritus does NOT become prepared."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])

        # Simulate only one creature dying
        dead1 = Creature(name="Dead One", base_power=1, base_toughness=1)
        game.record_creature_death(dead1)

        card.check_end_step_trigger(game)
        assert card.is_prepared is False

    def test_does_not_become_prepared_with_zero_deaths(self) -> None:
        """If no creatures died, Emeritus does NOT become prepared."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])

        card.check_end_step_trigger(game)
        assert card.is_prepared is False

    def test_stays_prepared_if_already_prepared(self) -> None:
        """If already prepared and 2+ creatures died, remains prepared (no-op)."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = True
        set_board_state(game, 0, battlefield=[card])

        dead1 = Creature(name="Dead One", base_power=1, base_toughness=1)
        dead2 = Creature(name="Dead Two", base_power=2, base_toughness=2)
        game.record_creature_death(dead1)
        game.record_creature_death(dead2)

        card.check_end_step_trigger(game)
        assert card.is_prepared is True

    def test_three_deaths_also_triggers(self) -> None:
        """Three or more deaths should also satisfy the 'two or more' condition."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])

        for i in range(3):
            dead = Creature(name=f"Dead {i}", base_power=1, base_toughness=1)
            game.record_creature_death(dead)

        card.check_end_step_trigger(game)
        assert card.is_prepared is True

    def test_trigger_only_on_controllers_end_step(self) -> None:
        """The trigger fires at the beginning of YOUR end step, not opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])

        dead1 = Creature(name="Dead One", base_power=1, base_toughness=1)
        dead2 = Creature(name="Dead Two", base_power=2, base_toughness=2)
        game.record_creature_death(dead1)
        game.record_creature_death(dead2)

        # If it's the opponent's end step, should not trigger
        event = EndStepTriggeredEvent(player=p2)
        condition_met = card.end_step_condition(game, event)
        assert condition_met is False

    def test_trigger_fires_on_controllers_end_step(self) -> None:
        """The trigger condition is met when it's the controller's end step."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])

        dead1 = Creature(name="Dead One", base_power=1, base_toughness=1)
        dead2 = Creature(name="Dead Two", base_power=2, base_toughness=2)
        game.record_creature_death(dead1)
        game.record_creature_death(dead2)

        event = EndStepTriggeredEvent(player=p1)
        condition_met = card.end_step_condition(game, event)
        assert condition_met is True
