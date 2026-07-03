"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase, Step
from test_utils import (
    TestSetupError as SetupError,
    advance_to_phase,
    cast_spell,
    create_game,
    set_board_state,
)


def _mana_instance(land, player, index):
    ma = land.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ma.cost,
        effect=ma.mana_produced,
        is_mana_ability=True,
    )


def _activated_instance(land, player, index=0):
    aa = land.get_activated_abilities()[index]
    return ActivatedAbilityInstance(
        source=land, controller=player, cost=aa.cost, effect=aa.effect
    )


def _animate(game, land, p1) -> None:
    set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
    activate_ability(game, p1, _activated_instance(land, p1))
    priority_loop(game)


class TestBiblioplexMana:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        activate_ability(game, p1, _mana_instance(land, p1, 0))
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped

    def test_restricted_mana_pays_instant_only(self) -> None:
        game = create_game(scripts=([ManaType.RED], []))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        activate_ability(game, p1, _mana_instance(land, p1, 1))
        assert p1.life == 19  # paid 1 life
        assert p1.mana_pool.get(ManaType.RED) == 1

        spell = Instant(name="Trick", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        set_board_state(game, 0, hand=[spell])
        cast_spell(game, 0, "Trick")
        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_cannot_pay_creature(self) -> None:
        game = create_game(scripts=([ManaType.GREEN], []))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        activate_ability(game, p1, _mana_instance(land, p1, 1))

        bear = Creature(
            name="Bear", base_power=2, base_toughness=2,
            mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
        )
        set_board_state(game, 0, hand=[bear])
        try:
            cast_spell(game, 0, "Bear")
            raised = False
        except SetupError:
            raised = True
        assert raised, "restricted mana must not pay for a creature spell"


class TestBiblioplexAnimation:
    def test_five_generic_animates_to_2_4_wizard(self) -> None:
        game = create_game(scripts=(["pass"] * 4, ["pass"] * 4))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        land.register_triggers(game)
        _animate(game, land, p1)

        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_pump_on_instant_and_reset_at_cleanup(self) -> None:
        game = create_game(scripts=(["pass"] * 6, ["pass"] * 6))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        land.register_triggers(game)
        _animate(game, land, p1)

        spell = Instant(name="Trick", mana_cost=ManaCost(generic=1))
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Trick")
        assert land.power == 3  # +1/+0 from the cast

        # End-of-turn cleanup resets the pump but keeps the animation.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2 and land.toughness == 4
        assert CardType.CREATURE in land.card_types
        assert "Wizard" in land.subtypes

    def test_no_reanimation_when_already_creature(self) -> None:
        game = create_game(scripts=(["pass"] * 8, ["pass"] * 8))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        land.register_triggers(game)
        _animate(game, land, p1)
        land.modified_power = 5  # marker to detect a re-animation reset

        _animate(game, land, p1)  # second activation: cost paid, no effect
        assert land.modified_power == 5

    def test_restricted_mana_cannot_pay_animation(self) -> None:
        game = create_game(scripts=([ManaType.BLUE] * 5, []))
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[land])
        # 5 restricted blue mana — unusable for the {5} ability.
        for _ in range(5):
            p1.mana_pool.add_restricted(ManaType.BLUE, 1)
        from engine.abilities import AbilityError

        try:
            activate_ability(game, p1, _activated_instance(land, p1))
            raised = False
        except AbilityError:
            raised = True
        assert raised
