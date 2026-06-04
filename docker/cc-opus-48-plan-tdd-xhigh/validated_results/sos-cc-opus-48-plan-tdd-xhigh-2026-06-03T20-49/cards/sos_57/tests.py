"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, _resolve_top_of_stack


def _wizard(name="Wizard"):
    return Creature(name=name, subtypes={"Wizard"}, base_power=1, base_toughness=1)


def _put_spell_on_stack(game, owner, name="Big Spell", cost="{3}{R}"):
    """Simulate an opponent's spell already on the stack."""
    spell = Sorcery(name=name, mana_cost=ManaCost.parse(cost))
    spell.owner = owner
    spell.controller = owner
    owner.zones[Zone.STACK].add(spell)
    obj = StackObject(source=spell, controller=owner)
    game.stack.push(obj)
    return spell, obj


class TestProperties:
    def test_is_instant(self):
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self):
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self):
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestCounter:
    def test_counters_target_spell(self):
        game = create_game()
        p0, p1 = game.players
        spell, obj = _put_spell_on_stack(game, p1)
        ms = ManaSculpt(owner=None)
        set_board_state(game, 0, hand=[ms],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        p0._script.append(obj)  # choose_target
        engine_cast(game, p0, ms)
        # Resolve Mana Sculpt (top of stack).
        top = game.stack.pop()
        top.on_resolve(game)
        # Countered spell is now in its owner's graveyard, off the stack.
        assert spell in p1.zones[Zone.GRAVEYARD].get_all()
        assert all(o.source is not spell for o in game.stack.objects())


class TestDelayedMana:
    def _counter_with_wizard(self, game, control_wizard, cost="{3}{R}"):
        p0, p1 = game.players
        spell, obj = _put_spell_on_stack(game, p1, cost=cost)
        ms = ManaSculpt(owner=None)
        bf = [_wizard()] if control_wizard else []
        set_board_state(game, 0, hand=[ms], battlefield=bf,
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        p0._script.append(obj)
        engine_cast(game, p0, ms)
        top = game.stack.pop()
        top.on_resolve(game)
        return ms

    def test_wizard_adds_colorless_at_next_main_phase(self):
        game = create_game()
        p0 = game.players[0]
        self._counter_with_wizard(game, control_wizard=True, cost="{3}{R}")
        # cmc of countered spell = 4 -> {C}{C}{C}{C} at next main phase.
        p0.mana_pool.empty()
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p0, is_precombat=True))
        _resolve_top_of_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 4

    def test_no_wizard_no_mana(self):
        game = create_game()
        p0 = game.players[0]
        self._counter_with_wizard(game, control_wizard=False)
        p0.mana_pool.empty()
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p0, is_precombat=True))
        _resolve_top_of_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_mana_only_for_controller(self):
        game = create_game()
        p0, p1 = game.players
        self._counter_with_wizard(game, control_wizard=True)
        p0.mana_pool.empty()
        # Opponent's main phase should not grant the mana.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True))
        _resolve_top_of_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_delayed_mana_is_one_shot(self):
        game = create_game()
        p0 = game.players[0]
        self._counter_with_wizard(game, control_wizard=True, cost="{3}{R}")
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p0, is_precombat=True))
        _resolve_top_of_stack(game)
        p0.mana_pool.empty()
        # A subsequent main phase should not add more mana.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p0, is_precombat=False))
        _resolve_top_of_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
