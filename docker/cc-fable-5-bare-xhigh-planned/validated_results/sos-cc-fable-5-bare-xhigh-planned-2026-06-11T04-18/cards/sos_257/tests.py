"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _activate_mana(game, player, land, index):
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


def _activate_animation(game, player, land):
    ability = land.get_activated_abilities()[0]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=land,
            controller=player,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        ),
    )
    player._script.extend(["pass"])
    game.players[1 - game.players.index(player)]._script.extend(["pass"])
    priority_loop(game)


class TestManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        _activate_mana(game, p1, land, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped

    def test_tapped_land_cannot_activate_again(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        _activate_mana(game, p1, land, 0)
        with pytest.raises(AbilityError):
            _activate_mana(game, p1, land, 0)

    def test_restricted_mana_costs_a_life_and_casts_instants_only(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        spell = Instant(name="Cheap Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[land], hand=[spell])
        p1._script.extend([ManaType.BLUE])
        _activate_mana(game, p1, land, 1)
        assert p1.life == 19
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 1
        cast_spell(game, 0, "Cheap Trick")
        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 0

    def test_restricted_mana_cannot_pay_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{G}"), base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[land], hand=[bear])
        p1._script.extend([ManaType.GREEN])
        _activate_mana(game, p1, land, 1)
        try:
            cast_spell(game, 0, "Bear")
            raised = False
        except Exception:
            raised = True
        assert raised, "restricted mana must not pay for a creature spell"


class TestAnimation:
    def test_becomes_2_4_wizard_still_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_animation(game, p1, land)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes
        assert land.power == 2
        assert land.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_not_a_creature_before_animation(self) -> None:
        land = GreatHallOfTheBiblioplex()
        assert CardType.CREATURE not in land.card_types
        assert not hasattr(land, "power")
        assert not hasattr(land, "toughness")

    def test_second_activation_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})
        _activate_animation(game, p1, land)
        _activate_animation(game, p1, land)
        assert land.power == 2
        # Exactly one pump trigger registered: a single cast gives +1, not +2.
        spell = Instant(name="Trick", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Trick")
        assert land.power == 3

    def test_pump_stacks_per_spell_and_expires_end_of_turn(self) -> None:
        from engine.turn import run_turn

        game = create_game(deck2=[Instant(name=f"D{i}", mana_cost=ManaCost.parse("{1}")) for i in range(8)])
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        s1 = Instant(name="One", mana_cost=ManaCost.parse("{1}"))
        s2 = Instant(name="Two", mana_cost=ManaCost.parse("{1}"))
        set_board_state(
            game, 0, battlefield=[land],
            hand=[s1, s2],
            mana={ManaType.COLORLESS: 7},
        )
        _activate_animation(game, p1, land)
        cast_spell(game, 0, "One")
        cast_spell(game, 0, "Two")
        assert land.power == 4  # 2 + 1 + 1
        assert land.toughness == 4
        # Finish the turn (hand p2's empty turn through cleanup): pump expires.
        game.active_player_index = 1
        game.priority_player_index = 1
        run_turn(game)
        assert land.power == 2

    def test_opponent_spells_do_not_pump(self) -> None:
        game = create_game()
        p1, p2 = game.players
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_animation(game, p1, land)
        spell = Instant(name="Theirs", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.COLORLESS: 1})
        game.active_player_index = 1
        game.priority_player_index = 1
        cast_spell(game, 1, "Theirs")
        assert land.power == 2
