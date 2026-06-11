"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.casting import play_land
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _play_great_hall(game, player_index=0):
    hall = GreatHallOfTheBiblioplex()
    set_board_state(game, player_index, hand=[hall])
    game.active_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    play_land(game, game.players[player_index], hall)
    return hall


def _activate_mana(game, player, hall, index):
    ability = hall.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=hall,
        controller=player,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
    )
    activate_ability(game, player, inst)


def _activate_animation(game, player, hall):
    ability = hall.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(
        source=hall, controller=player, cost=ability.cost, effect=ability.effect,
    )
    activate_ability(game, player, inst)
    game.players[0]._script.append("pass")
    game.players[1]._script.append("pass")
    priority_loop(game)


class TestManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        p1 = game.players[0]
        hall = _play_great_hall(game)
        _activate_mana(game, p1, hall, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped

    def test_pay_life_for_restricted_color(self):
        game = create_game(scripts=([ManaType.RED], []))
        p1 = game.players[0]
        hall = _play_great_hall(game)
        _activate_mana(game, p1, hall, 1)
        assert p1.life == 19
        assert hall.is_tapped
        assert p1.mana_pool.get_restricted(ManaType.RED) == 1
        assert p1.mana_pool.get(ManaType.RED) == 0

    def test_restricted_mana_cannot_pay_for_creature(self):
        game = create_game(scripts=([ManaType.RED], []))
        p1 = game.players[0]
        hall = _play_great_hall(game)
        _activate_mana(game, p1, hall, 1)
        bear = Creature(
            name="Bear", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{R}"),
        )
        set_board_state(game, 0, hand=[bear])
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")
        # ...but it can pay for an instant.
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[probe])
        cast_spell(game, 0, "Probe")
        assert p1.mana_pool.get_restricted(ManaType.RED) == 0


class TestAnimation:
    def test_becomes_2_4_wizard_still_land(self):
        game = create_game()
        p1 = game.players[0]
        hall = _play_great_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_animation(game, p1, hall)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_no_effect_if_already_creature(self):
        game = create_game()
        p1 = game.players[0]
        hall = _play_great_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 10})
        _activate_animation(game, p1, hall)
        _activate_animation(game, p1, hall)
        assert hall.power == 2
        assert hall.toughness == 4

    def test_not_a_creature_before_animation(self):
        hall = GreatHallOfTheBiblioplex()
        assert CardType.CREATURE not in hall.card_types
        assert not hasattr(hall, "toughness")  # SBAs must not see a 0-toughness

    def test_pump_per_instant_and_reset_at_end_of_turn(self):
        from engine.turn import run_turn

        # p1's deck covers the draw step during run_turn.
        filler = [Instant(name=f"F{i}", mana_cost=ManaCost.parse("{9}")) for i in range(9)]
        game = create_game(deck1=filler, scripts=([], []))
        p1 = game.players[0]
        hall = _play_great_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate_animation(game, p1, hall)

        set_board_state(
            game, 0,
            hand=[Instant(name="Probe A", mana_cost=ManaCost.parse("{1}")),
                  Instant(name="Probe B", mana_cost=ManaCost.parse("{1}"))],
            mana={ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Probe A")
        assert hall.power == 3
        cast_spell(game, 0, "Probe B")
        assert hall.power == 4
        assert hall.toughness == 4

        # Run the rest of the turn — the pump expires during cleanup.
        p1._script.append(None)  # declare no attackers
        run_turn(game)
        assert hall.power == 2
