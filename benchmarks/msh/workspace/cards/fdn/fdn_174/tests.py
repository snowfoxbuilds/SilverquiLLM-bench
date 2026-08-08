"""Regression test for FDN 174 — Fake Your Own Death.

The crash surface is spell **resolution leaving the stack**: ``on_resolve``
registered an end-of-turn cleanup trigger behind a ``hasattr(EventType, ...)``
guard on an undefined ``EventType`` name, so every resolution raised
``NameError`` (`resolve Fake Your Own Death (stack exit)` in the replay layer).
This test drives ``on_resolve`` and asserts the whole resolution completes:
the +2/+0 buff applies and both the death trigger and its end-of-turn cleanup
trigger are registered.
"""

from __future__ import annotations

from cards.fdn.fdn_174.card_impl import FakeYourOwnDeath
from engine.card import Creature, Instant
from engine.events import CreatureDiesTriggeredEvent, EndOfTurnTriggeredEvent
from engine.types import ManaCost
from test_utils import create_game, set_board_state


class TestFakeYourOwnDeathProperties:
    def test_is_instant(self) -> None:
        assert isinstance(FakeYourOwnDeath(owner=None), Instant)

    def test_mana_cost(self) -> None:
        assert FakeYourOwnDeath(owner=None).mana_cost == ManaCost.parse("{1}{B}")


class TestFakeYourOwnDeathResolution:
    """The previously-crashing stack-exit resolution path."""

    def _resolve_on_target(self):
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Bear", subtypes={"Bear"}, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        spell = FakeYourOwnDeath(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)  # must not raise NameError
        return game, spell, target

    def test_resolution_does_not_raise_and_applies_buff(self) -> None:
        game, spell, target = self._resolve_on_target()
        # The +2/+0 buff is a continuous effect sourced by the spell.
        assert game.effect_manager.get_effects_by_source(spell)
        game.effect_manager.apply_all(game)
        assert target.power == 4  # 2 base + 2
        assert target.toughness == 2

    def test_registers_death_and_eot_cleanup_triggers(self) -> None:
        game, spell, target = self._resolve_on_target()
        event_types = {t.event_type for t in game.trigger_manager.get_triggers()}
        # The death trigger and the end-of-turn cleanup (the line that used to
        # crash) are both registered.
        assert CreatureDiesTriggeredEvent in event_types
        assert EndOfTurnTriggeredEvent in event_types

    def test_no_target_is_a_safe_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FakeYourOwnDeath(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)  # fizzles cleanly
        assert game.effect_manager.get_effects_by_source(spell) == []
