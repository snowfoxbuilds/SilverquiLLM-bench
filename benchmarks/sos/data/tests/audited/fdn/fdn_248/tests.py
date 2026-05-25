"""Audited tests for FDN 248 — Thousand-Year Storm."""
from __future__ import annotations

import pytest

from card_impl import ThousandYearStorm
from benchmarks.sos.workspace.engine.card import Creature, Enchantment, Instant, Sorcery
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.tests.test_utils import create_game


def _push_spell(game, spell, player) -> StackObject:
    """Push *spell* as a StackObject and return it."""
    so = StackObject(source=spell, controller=player)
    game.stack.push(so)
    return so


def _fire_and_resolve_trigger(game, storm, spell, player) -> None:
    """Fire a SpellCastTriggeredEvent for *spell* then resolve only the trigger effect.

    The spell itself is left on the stack for the caller to inspect.
    """
    game.trigger_manager.fire_event(
        game, SpellCastTriggeredEvent(player=player, spell=spell)
    )
    # Trigger effect is on top; pop and resolve it.
    trigger_obj = game.stack.pop()
    trigger_obj.on_resolve(game)


class TestThousandYearStormBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = ThousandYearStorm(owner=None)
        assert card.name == 'Thousand-Year Storm'

    def test_mana_cost(self) -> None:
        card = ThousandYearStorm(owner=None)
        assert card.mana_cost == ManaCost.parse('{4}{U}{R}')

    def test_is_enchantment(self) -> None:
        card = ThousandYearStorm(owner=None)
        assert isinstance(card, Enchantment)


class TestThousandYearStormTrigger:
    """Storm trigger fires for controller's instants/sorceries only."""

    def _setup(self, game=None):
        if game is None:
            game = create_game()
        p1 = game.players[0]
        storm = ThousandYearStorm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(storm)
        storm.register_triggers(game)
        return game, p1, storm

    # ------------------------------------------------------------------
    # Filtering: what spells trigger storm
    # ------------------------------------------------------------------

    def test_creature_spell_does_not_trigger(self) -> None:
        """Creature spells must not increment the storm count."""
        game, p1, storm = self._setup()
        creature = Creature(
            name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(player=p1, spell=creature)
        )
        # No trigger should have been pushed.
        assert game.stack.is_empty()
        assert storm._storm_count == 0

    def test_opponent_spell_does_not_trigger(self) -> None:
        """A spell cast by the opponent must not trigger this player's storm."""
        game, p1, storm = self._setup()
        p2 = game.players[1]
        spell = Instant(name='Bolt', owner=p2, controller=p2)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(player=p2, spell=spell)
        )
        assert game.stack.is_empty()
        assert storm._storm_count == 0

    def test_sorcery_does_trigger(self) -> None:
        """Sorceries as well as instants must trigger storm."""
        game, p1, storm = self._setup()
        sorcery = Sorcery(name='Divination', owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(player=p1, spell=sorcery)
        )
        assert not game.stack.is_empty()

    # ------------------------------------------------------------------
    # Storm count tracking
    # ------------------------------------------------------------------

    def test_first_spell_increments_count_to_one(self) -> None:
        """First instant/sorcery cast moves storm_count from 0 to 1."""
        game, p1, storm = self._setup()
        spell = Instant(name='Bolt', owner=p1, controller=p1)
        _push_spell(game, spell, p1)
        _fire_and_resolve_trigger(game, storm, spell, p1)
        assert storm._storm_count == 1

    def test_storm_count_resets_on_new_turn(self) -> None:
        """storm_count must reset to 0 at the start of a new turn."""
        game, p1, storm = self._setup()
        # Simulate two spells cast this turn.
        storm._storm_count = 2
        storm._last_turn = game.turn_number

        # Advance the turn number.
        game.turn_number += 1

        # Cast one spell on the new turn.
        spell = Instant(name='Shock', owner=p1, controller=p1)
        _push_spell(game, spell, p1)
        _fire_and_resolve_trigger(game, storm, spell, p1)

        # Count resets to 0 then increments to 1 for this spell.
        assert storm._storm_count == 1

    # ------------------------------------------------------------------
    # Stack copy behaviour
    # ------------------------------------------------------------------

    def test_first_spell_no_stack_copies(self) -> None:
        """The first spell cast this turn produces zero copies."""
        game, p1, storm = self._setup()
        spell = Instant(name='Bolt', owner=p1, controller=p1)
        so = _push_spell(game, spell, p1)
        _fire_and_resolve_trigger(game, storm, spell, p1)
        # Only the original spell remains on the stack.
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

    def test_second_spell_one_stack_copy(self) -> None:
        """The second instant/sorcery this turn generates exactly one copy."""
        game, p1, storm = self._setup()

        # First spell (no copies produced).
        spell1 = Instant(name='Bolt1', owner=p1, controller=p1)
        so1 = _push_spell(game, spell1, p1)
        _fire_and_resolve_trigger(game, storm, spell1, p1)
        game.stack.pop()  # resolve spell1

        # Second spell.
        spell2 = Instant(name='Bolt2', owner=p1, controller=p1)
        so2 = _push_spell(game, spell2, p1)
        _fire_and_resolve_trigger(game, storm, spell2, p1)

        # Stack: original spell2 + 1 copy.
        assert len(game.stack) == 2
        assert storm._storm_count == 2

    def test_third_spell_two_stack_copies(self) -> None:
        """The third instant/sorcery this turn generates exactly two copies."""
        game, p1, storm = self._setup()

        for i in range(2):
            s = Instant(name=f'Spell{i}', owner=p1, controller=p1)
            _push_spell(game, s, p1)
            _fire_and_resolve_trigger(game, storm, s, p1)
            # Drain original + any copies produced.
            while not game.stack.is_empty():
                game.stack.pop()

        spell3 = Instant(name='Spell3', owner=p1, controller=p1)
        so3 = _push_spell(game, spell3, p1)
        _fire_and_resolve_trigger(game, storm, spell3, p1)

        # Stack: original spell3 + 2 copies.
        assert len(game.stack) == 3
        assert storm._storm_count == 3

    def test_copies_call_on_resolve(self) -> None:
        """Each copy must call the original spell's on_resolve when it resolves."""
        game, p1, storm = self._setup()
        storm._storm_count = 1  # pre-seed so the next spell produces 1 copy

        resolved = []
        spell = Instant(name='Tracker', owner=p1, controller=p1)
        spell.on_resolve = lambda g: resolved.append('resolved')

        so = _push_spell(game, spell, p1)
        _fire_and_resolve_trigger(game, storm, spell, p1)

        # Stack now: [so (spell), copy]
        assert len(game.stack) == 2

        # Resolve the copy (top of stack).
        copy_obj = game.stack.pop()
        copy_obj.on_resolve(game)

        assert resolved == ['resolved']

    def test_copy_source_is_independent_of_original(self) -> None:
        """The copy's source card must be a distinct object from the original."""
        game, p1, storm = self._setup()
        storm._storm_count = 1  # produce 1 copy on next cast

        spell = Instant(name='Clone Test', owner=p1, controller=p1)
        so = _push_spell(game, spell, p1)
        _fire_and_resolve_trigger(game, storm, spell, p1)

        copy_obj = game.stack.pop()
        assert copy_obj.source is not spell
