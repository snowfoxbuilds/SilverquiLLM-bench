"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.types import CardType, ManaCost, ManaType
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _activate_mana(game, player, land, index):
    """Activate a printed mana ability through the engine's ability path."""
    ability = land.get_mana_abilities()[index]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=land,
            controller=player,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
        ),
    )


def _activate(game, player, land, index):
    """Activate a printed activated ability and resolve it off the stack."""
    ability = land.get_activated_abilities()[index]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=land,
            controller=player,
            cost=ability.cost,
            effect=ability.effect,
        ),
    )
    resolve_top(game)


def _setup():
    game = create_game()
    p1 = game.players[0]
    hall = GreatHallOfTheBiblioplex(owner=p1)
    set_board_state(game, 0, battlefield=[hall])
    hall.register_triggers(game)
    return game, p1, hall


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self):
        game, p1, hall = _setup()
        _activate_mana(game, p1, hall, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped
        with pytest.raises(AbilityError):
            _activate_mana(game, p1, hall, 0)

    def test_restricted_mana_casts_instant(self):
        game, p1, hall = _setup()
        p1._script.append(ManaType.BLUE)  # color choice
        _activate_mana(game, p1, hall, 1)
        assert p1.life == 19
        assert hall.is_tapped
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.BLUE) == 0
        spell = Instant(name="Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, hand=[spell])
        cast_spell(game, 0, "Trick")
        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 0

    def test_restricted_mana_cannot_cast_creature(self):
        game, p1, hall = _setup()
        p1._script.append(ManaType.GREEN)
        _activate_mana(game, p1, hall, 1)
        bear = Creature(
            name="Bear", mana_cost=ManaCost.parse("{G}"),
            base_power=2, base_toughness=2,
        )
        set_board_state(game, 0, hand=[bear])
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")


class TestGreatHallAnimation:
    def test_five_mana_animates_to_2_4_wizard(self):
        game, p1, hall = _setup()
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _activate(game, p1, hall, 0)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_animation_requires_five_mana(self):
        game, p1, hall = _setup()
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 4})
        with pytest.raises(AbilityError):
            _activate(game, p1, hall, 0)
        assert CardType.CREATURE not in hall.card_types

    def test_pump_on_instant_cast_resets_end_of_turn(self):
        from engine.turn import run_turn

        game, p1, hall = _setup()
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _activate(game, p1, hall, 0)
        spells = [
            Instant(name=f"Trick {i}", mana_cost=ManaCost.parse("{1}"))
            for i in range(2)
        ]
        set_board_state(game, 0, hand=spells, mana={ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Trick 0")
        assert hall.power == 3
        cast_spell(game, 0, "Trick 1")
        assert hall.power == 4
        # Finish the turn through the real turn loop; pump expires.
        p1._script.append(None)  # decline to attack with the animated land
        run_turn(game)
        assert hall.power == 2

    def test_no_pump_while_not_animated(self):
        game, p1, hall = _setup()
        spell = Instant(name="Trick", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Trick")
        assert CardType.CREATURE not in hall.card_types
        assert not hasattr(hall, "power") or hall.power == 0
