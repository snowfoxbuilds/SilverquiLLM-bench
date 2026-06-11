"""Tests for SOS 257 — Great Hall of the Biblioplex (land: mana + restriction + animation)."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.casting import resolve_top
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, cast_spell, set_board_state


class Dummy(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Dummy")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


def _activate_mana(game, player, land, index):
    ma = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land, controller=player, cost=ma.cost,
        effect=ma.mana_produced, is_mana_ability=True,
    )
    activate_ability(game, player, inst)


def _activate(game, player, land, index):
    aa = land.get_activated_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land, controller=player, cost=aa.cost,
        effect=aa.effect, is_mana_ability=False,
    )
    activate_ability(game, player, inst)
    resolve_top(game)  # non-mana ability resolves off the stack


def _land_on(game, player_index=0):
    land = GreatHallOfTheBiblioplex(owner=None)
    set_board_state(game, player_index, battlefield=[land])
    return land


class TestProperties:
    def test_is_land(self):
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert card.name == "Great Hall of the Biblioplex"
        assert card.can_cast(None) is False


class TestManaAbilities:
    def test_colorless_mana(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        _activate_mana(game, p0, land, 0)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped

    def test_restricted_mana_costs_life(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        p0._script.append(ManaType.BLUE)  # chosen color
        _activate_mana(game, p0, land, 1)
        assert p0.life == 19
        assert p0.mana_pool.get(ManaType.BLUE) == 1
        assert land.is_tapped

    def test_restricted_mana_cannot_pay_creature(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        p0._script.append(ManaType.RED)
        _activate_mana(game, p0, land, 1)
        creature = Creature(name="Goblin", mana_cost=ManaCost.parse("{R}"),
                            base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[creature])
        with pytest.raises(Exception):
            cast_spell(game, 0, "Goblin")

    def test_restricted_mana_pays_instant(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        p0._script.append(ManaType.RED)
        _activate_mana(game, p0, land, 1)
        set_board_state(game, 0, hand=[Dummy(owner=None)])
        cast_spell(game, 0, "Dummy")
        assert any(c.name == "Dummy" for c in game.get_graveyard(p0).get_all())


class TestAnimation:
    def test_becomes_2_4_wizard_still_land(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate(game, p0, land, 0)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert p0.mana_pool.total() == 0

    def test_restricted_mana_cannot_pay_animation(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        p0.mana_pool.add(ManaType.RED, 5, restricted=True)  # only restricted mana
        with pytest.raises(Exception):
            _activate(game, p0, land, 0)
        assert CardType.CREATURE not in land.card_types

    def test_pump_on_instant_cast_and_eot_reset(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _activate(game, p0, land, 0)  # animate
        set_board_state(game, 0, mana={ManaType.RED: 2}, hand=[Dummy(), Dummy()])
        cast_spell(game, 0, "Dummy")
        assert land.power == 3  # +1/+0
        cast_spell(game, 0, "Dummy")
        assert land.power == 4  # stacks
        # End-of-turn reset happens via apply_all (run during cleanup).
        game.effect_manager.apply_all(game)
        assert land.power == 2
        assert CardType.CREATURE in land.card_types  # animation is permanent

    def test_animate_twice_is_noop(self):
        game = create_game()
        p0 = game.players[0]
        land = _land_on(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 10})
        _activate(game, p0, land, 0)
        _activate(game, p0, land, 0)  # already a creature → does nothing
        assert land.power == 2 and land.toughness == 4
