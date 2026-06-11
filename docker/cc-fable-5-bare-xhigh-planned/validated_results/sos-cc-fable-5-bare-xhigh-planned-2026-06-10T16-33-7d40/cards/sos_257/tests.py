"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Creature, Instant, Land
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import TestSetupError as SetupError
from test_utils import cast_spell, create_game, set_board_state


def _activate_mana(game: Any, player_index: int, land: Any, index: int) -> None:
    """Activate a mana ability by printed index (resolves immediately)."""
    player = game.players[player_index]
    ability = land.get_mana_abilities()[index]
    activate_ability(game, player, ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
    ))


def _activate(game: Any, player_index: int, land: Any, index: int) -> None:
    """Activate a regular activated ability by printed index and resolve it."""
    player = game.players[player_index]
    ability = land.get_activated_abilities()[index]
    activate_ability(game, player, ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
    ))
    for p in game.players:
        p._script.append("pass")
    priority_loop(game)


def _setup(mana=None):
    game = create_game()
    land = GreatHallOfTheBiblioplex(owner=None)
    set_board_state(game, 0, battlefield=[land], mana=mana or {})
    land.register_triggers(game)
    return game, land


class TestGreatHallProperties:
    def test_static_data(self) -> None:
        land = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(land, Land)
        assert land.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in land.card_types
        assert CardType.CREATURE not in land.card_types
        game = create_game()
        assert land.can_cast(game) is False


class TestManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game, land = _setup()
        _activate_mana(game, 0, land, 0)
        p0 = game.players[0]
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped
        with pytest.raises(AbilityError):
            _activate_mana(game, 0, land, 0)

    def test_restricted_mana_pays_for_instants_only(self) -> None:
        game, land = _setup()
        p0 = game.players[0]
        p0._script.append(ManaType.RED)
        _activate_mana(game, 0, land, 1)
        assert p0.life == 19
        assert land.is_tapped
        assert p0.mana_pool.get_restricted(ManaType.RED) == 1
        assert p0.mana_pool.total() == 0

        # A creature spell cannot be paid with the restricted mana.
        bear = Creature(
            name="Bear", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{R}"),
        )
        set_board_state(game, 0, hand=[bear])
        with pytest.raises(SetupError):
            cast_spell(game, 0, "Bear")

        # An instant can be.
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[probe])
        cast_spell(game, 0, "Probe")
        assert probe in p0.zones[Zone.GRAVEYARD].get_all()
        assert p0.mana_pool.get_restricted(ManaType.RED) == 0


class TestAnimation:
    def test_five_mana_animates_to_2_4_wizard(self) -> None:
        game, land = _setup(mana={ManaType.COLORLESS: 5})
        _activate(game, 0, land, 0)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert game.players[0].mana_pool.total() == 0

    def test_animation_noop_if_already_creature(self) -> None:
        game, land = _setup(mana={ManaType.COLORLESS: 10})
        _activate(game, 0, land, 0)
        _activate(game, 0, land, 0)
        assert land.power == 2 and land.toughness == 4
        assert CardType.CREATURE in land.card_types

    def test_animated_pump_per_spell_and_reset_at_end_of_turn(self) -> None:
        from engine.turn import run_turn

        game, land = _setup(mana={ManaType.COLORLESS: 5})
        _activate(game, 0, land, 0)

        p0 = game.players[0]
        spells = [
            Instant(name=f"Probe{i}", mana_cost=ManaCost.parse("{U}"))
            for i in range(2)
        ]
        set_board_state(game, 0, hand=spells, mana={ManaType.BLUE: 2})
        cast_spell(game, 0, "Probe0")
        assert land.power == 3
        cast_spell(game, 0, "Probe1")
        assert land.power == 4
        assert land.toughness == 4

        # Pump resets during cleanup at end of turn.  The animated land is
        # an eligible attacker, so script "attack with nothing".
        p0._script.append([])
        run_turn(game)
        assert land.power == 2

    def test_unanimated_land_does_not_pump(self) -> None:
        game, land = _setup()
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, hand=[probe], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert CardType.CREATURE not in land.card_types
        assert land.power == 0
