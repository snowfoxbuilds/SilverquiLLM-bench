"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Instant, Creature
from engine.casting import resolve_top
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import TestSetupError, create_game, cast_spell, set_board_state


def _activate_mana(game, land, index):
    """Activate a printed mana ability by index through the engine."""
    ability = land.get_mana_abilities()[index]
    instance = ActivatedAbilityInstance(
        source=land,
        controller=land.controller,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
    )
    activate_ability(game, land.controller, instance)


def _activate(game, land, index):
    """Activate a printed (non-mana) activated ability by index."""
    ability = land.get_activated_abilities()[index]
    instance = ActivatedAbilityInstance(
        source=land,
        controller=land.controller,
        cost=ability.cost,
        effect=ability.effect,
    )
    activate_ability(game, land.controller, instance)
    resolve_top(game)


def _setup_land(game):
    p1 = game.players[0]
    land = GreatHallOfTheBiblioplex(owner=p1)
    set_board_state(game, 0, battlefield=[land])
    land.register_triggers(game)
    return land


class TestManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        p1 = game.players[0]
        land = _setup_land(game)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        _activate_mana(game, land, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped

    def test_tapped_land_cannot_activate(self):
        game = create_game()
        land = _setup_land(game)
        land.is_tapped = True
        with pytest.raises(AbilityError):
            _activate_mana(game, land, 0)

    def test_restricted_mana_casts_instant(self):
        """Second ability: pay 1 life, add a chosen color usable for an
        instant spell."""
        game = create_game()
        p1 = game.players[0]
        land = _setup_land(game)
        p1._script.append(ManaType.BLUE)  # color choice
        _activate_mana(game, land, 1)
        assert p1.life == 19
        assert land.is_tapped
        assert p1.mana_pool.get(ManaType.BLUE) == 1

        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, hand=[spell])
        cast_spell(game, 0, "Probe")
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_cannot_cast_creature(self):
        game = create_game()
        p1 = game.players[0]
        land = _setup_land(game)
        p1._script.append(ManaType.GREEN)
        _activate_mana(game, land, 1)

        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{G}"))
        bear.owner = bear.controller = p1
        p1.zones[Zone.HAND].add(bear)
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")
        # The restricted mana is still there, unspent.
        assert p1.mana_pool.get(ManaType.GREEN) == 1


class TestAnimation:
    def test_becomes_2_4_wizard_still_a_land(self):
        game = create_game()
        p1 = game.players[0]
        land = _setup_land(game)
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        _activate(game, land, 0)

        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes
        assert land.power == 2
        assert land.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_animation_requires_five_mana(self):
        game = create_game()
        p1 = game.players[0]
        land = _setup_land(game)
        p1.mana_pool.add(ManaType.COLORLESS, 4)
        with pytest.raises(AbilityError):
            _activate(game, land, 0)
        assert CardType.CREATURE not in land.card_types

    def test_already_a_creature_no_double_animation(self):
        """Second activation pays but has no effect (single pump trigger)."""
        game = create_game()
        p1 = game.players[0]
        land = _setup_land(game)
        p1.mana_pool.add(ManaType.COLORLESS, 10)
        _activate(game, land, 0)
        _activate(game, land, 0)

        triggers = game.trigger_manager.get_triggers_for_source(land)
        # one pump trigger only (register_triggers itself adds none)
        assert len(triggers) == 1
        assert land.power == 2

    def test_pump_on_instant_cast(self):
        """After animation, each of your instant/sorcery casts gives +1/+0."""
        game = create_game()
        p1 = game.players[0]
        land = _setup_land(game)
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        _activate(game, land, 0)

        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Probe")
        assert land.power == 3
        assert land.toughness == 4

    def test_opponent_cast_does_not_pump(self):
        game = create_game()
        p1, p2 = game.players
        land = _setup_land(game)
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        _activate(game, land, 0)

        spell = Instant(name="Opp Probe", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 1, "Opp Probe")
        assert land.power == 2
