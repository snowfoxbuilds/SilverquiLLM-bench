"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _mana_ability_instance(land, player, index: int) -> ActivatedAbilityInstance:
    ability = land.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
        description=ability.description,
    )


def _animate(game, land, player) -> None:
    """Activate the {5} ability through the real engine and resolve it."""
    ability = land.get_activated_abilities()[0]
    instance = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
        description=ability.description,
    )
    activate_ability(game, player, instance)
    player._script.extend(["pass", "pass"])
    game.players[1]._script.extend(["pass", "pass"])
    priority_loop(game)


class TestManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])

        activate_ability(game, p1, _mana_ability_instance(land, p1, 0))

        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped

    def test_restricted_mana_pays_for_instant_only(self) -> None:
        """Pay 1 life for restricted {R}: casts an instant, not a creature."""
        game = create_game(scripts=([ManaType.RED], []))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        spell = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"))
        wolf = Creature(name="Wolf", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[land], hand=[spell, wolf])
        life0 = p1.life

        activate_ability(game, p1, _mana_ability_instance(land, p1, 1))
        assert p1.life == life0 - 1
        assert land.is_tapped
        assert p1.mana_pool.restricted_total() == 1

        # The restricted mana cannot pay for a creature spell.
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Wolf")

        # But it pays for an instant.
        cast_spell(game, 0, "Shock")
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
        assert p1.mana_pool.restricted_total() == 0

    def test_life_tap_requires_untapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        land.is_tapped = True

        from engine.abilities import AbilityError

        with pytest.raises(AbilityError):
            activate_ability(game, p1, _mana_ability_instance(land, p1, 1))


class TestAnimation:
    def test_five_generic_becomes_2_4_wizard_still_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})

        _animate(game, land, p1)

        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_second_activation_noop_when_already_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        _animate(game, land, p1)
        triggers_after_first = len(game.trigger_manager.get_triggers_for_source(land))
        _animate(game, land, p1)

        assert land.power == 2 and land.toughness == 4
        # No duplicate pump trigger registered.
        assert len(game.trigger_manager.get_triggers_for_source(land)) == triggers_after_first


class TestAnimatedPump:
    def test_pump_per_spell_and_reset_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        s1 = Instant(name="Op1", mana_cost=ManaCost.parse("{U}"))
        s2 = Instant(name="Op2", mana_cost=ManaCost.parse("{U}"))
        set_board_state(
            game, 0, battlefield=[land], hand=[s1, s2],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 2},
        )
        _animate(game, land, p1)

        cast_spell(game, 0, "Op1")
        assert land.power == 3

        cast_spell(game, 0, "Op2")
        assert land.power == 4

        # Run out the rest of the turn — cleanup expires the pump.
        from engine.turn import run_turn

        run_turn(game)
        assert land.power == 2

    def test_opponent_spell_does_not_pump(self) -> None:
        game = create_game()
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _animate(game, land, game.players[0])

        spell = Instant(name="Their Spell", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 1, "Their Spell")

        assert land.power == 2
