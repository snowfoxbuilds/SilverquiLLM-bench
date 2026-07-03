"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


def _activate_mana_ability(game, player, land, index: int) -> None:
    """Activate the land's mana ability at its printed *index* through
    the engine's activation pipeline (mana abilities resolve immediately)."""
    ability = land.get_mana_abilities()[index]
    instance = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
    )
    activate_ability(game, player, instance)


def _activate_ability(game, player, land, index: int) -> None:
    """Activate a non-mana activated ability by printed index; it goes on
    the stack and resolves through the priority loop."""
    ability = land.get_activated_abilities()[index]
    instance = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
    )
    activate_ability(game, player, instance)
    player._script.extend(["pass"])
    game.players[1 - game.players.index(player)]._script.extend(["pass"])
    priority_loop(game)


def _hall_on_battlefield(game):
    hall = GreatHallOfTheBiblioplex(owner=None)
    set_board_state(game, 0, battlefield=[hall])
    return hall


class TestGreatHallProperties:
    def test_static_data(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert hall.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE not in hall.card_types


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        _activate_mana_ability(game, p1, hall, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped
        # Tapped — cannot activate again.
        with pytest.raises(AbilityError):
            _activate_mana_ability(game, p1, hall, 0)

    def test_pay_life_for_restricted_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        p1._script.append(ManaType.BLUE)  # color choice
        _activate_mana_ability(game, p1, hall, 1)
        assert p1.life == 19
        assert hall.is_tapped
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.BLUE) == 0  # not in the open pool

    def test_restricted_mana_casts_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        p1._script.append(ManaType.BLUE)
        _activate_mana_ability(game, p1, hall, 1)
        spell = Instant(name="Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, hand=[spell])
        cast_spell(game, 0, "Trick")
        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 0

    def test_restricted_mana_cannot_cast_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        p1._script.append(ManaType.GREEN)
        _activate_mana_ability(game, p1, hall, 1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{G}"))
        set_board_state(game, 0, hand=[bear])
        with pytest.raises(Exception):
            cast_spell(game, 0, "Bear")
        assert p1.mana_pool.get_restricted(ManaType.GREEN) == 1


class TestGreatHallAnimation:
    def test_animation_becomes_2_4_wizard_still_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})
        _activate_ability(game, p1, hall, 0)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert p1.mana_pool.total() == 0  # {5} paid

    def test_pump_on_instant_cast_stacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})
        _activate_ability(game, p1, hall, 0)
        spells = [Instant(name=f"Trick {i}", mana_cost=ManaCost.parse("{1}"))
                  for i in range(2)]
        set_board_state(game, 0, hand=list(spells),
                        mana={ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Trick 0")
        assert hall.power == 3 and hall.toughness == 4
        cast_spell(game, 0, "Trick 1")
        assert hall.power == 4 and hall.toughness == 4

    def test_second_activation_has_no_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 10})
        _activate_ability(game, p1, hall, 0)
        _activate_ability(game, p1, hall, 0)  # already a creature — no effect
        assert hall.power == 2 and hall.toughness == 4
        # Only one pump trigger registered.
        assert len(game.trigger_manager.get_triggers_for_source(hall)) == 1

    def test_unanimated_land_does_not_pump(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        spell = Instant(name="Trick", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Trick")
        assert CardType.CREATURE not in hall.card_types
        assert hall.power == 0
