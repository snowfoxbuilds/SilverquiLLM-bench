"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Instant, Land, Sorcery
from engine.types import CardType, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state, _resolve_top_of_stack


def _instant(name="Zap", cost="{R}"):
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _sorcery(name="Study", cost="{U}"):
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _animate(game, player, gh):
    """Activate the {5} animate ability through the engine and resolve it."""
    ability = gh.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(
        source=gh,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
    )
    activate_ability(game, player, inst)
    _resolve_top_of_stack(game)


class TestProperties:
    def test_is_land(self):
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_name(self):
        assert (
            GreatHallOfTheBiblioplex(owner=None).name
            == "Great Hall of the Biblioplex"
        )

    def test_is_land_type(self):
        assert CardType.LAND in GreatHallOfTheBiblioplex(owner=None).card_types

    def test_not_creature_initially(self):
        assert CardType.CREATURE not in GreatHallOfTheBiblioplex(owner=None).card_types

    def test_has_two_mana_abilities(self):
        assert len(GreatHallOfTheBiblioplex(owner=None).get_mana_abilities()) == 2


class TestColorlessMana:
    def test_taps_for_colorless(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh])
        ability = gh.get_mana_abilities()[0]
        assert ability.cost(game, gh) is True
        ability.mana_produced(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert gh.is_tapped is True

    def test_requires_untapped(self):
        game = create_game()
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh])
        gh.is_tapped = True
        ability = gh.get_mana_abilities()[0]
        assert ability.cost(game, gh) is False


class TestAnyColorMana:
    def test_pays_life_and_adds_chosen_color(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], life=20)
        p0._script.append(ManaType.RED)
        ability = gh.get_mana_abilities()[1]
        assert ability.cost(game, gh) is True
        ability.mana_produced(game)
        assert p0.mana_pool.get(ManaType.RED) == 1
        assert p0.life == 19
        assert gh.is_tapped is True

    def test_any_color_requires_untapped(self):
        game = create_game()
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh])
        gh.is_tapped = True
        ability = gh.get_mana_abilities()[1]
        assert ability.cost(game, gh) is False


class TestAnimation:
    def test_five_mana_makes_a_wizard_creature(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], mana={ManaType.COLORLESS: 5})
        gh.register_triggers(game)
        _animate(game, p0, gh)
        assert CardType.CREATURE in gh.card_types
        assert "Wizard" in gh.subtypes
        assert gh.power == 2
        assert gh.toughness == 4

    def test_still_a_land_after_animation(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], mana={ManaType.COLORLESS: 5})
        gh.register_triggers(game)
        _animate(game, p0, gh)
        assert CardType.LAND in gh.card_types

    def test_animation_spends_five(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], mana={ManaType.COLORLESS: 5})
        gh.register_triggers(game)
        _animate(game, p0, gh)
        assert p0.mana_pool.total() == 0

    def test_cannot_animate_without_five(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], mana={ManaType.COLORLESS: 4})
        with pytest.raises(AbilityError):
            _animate(game, p0, gh)
        assert CardType.CREATURE not in gh.card_types


class TestCastBuff:
    def test_buff_after_animation(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(
            game,
            0,
            battlefield=[gh],
            hand=[_instant("Zap")],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 1},
        )
        gh.register_triggers(game)
        _animate(game, p0, gh)
        cast_spell(game, 0, "Zap")
        assert gh.power == 3
        assert gh.toughness == 4

    def test_buff_is_cumulative(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(
            game,
            0,
            battlefield=[gh],
            hand=[_instant("Zap"), _sorcery("Study")],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 1, ManaType.BLUE: 1},
        )
        gh.register_triggers(game)
        _animate(game, p0, gh)
        cast_spell(game, 0, "Zap")
        cast_spell(game, 0, "Study")
        assert gh.power == 4

    def test_no_buff_before_animation(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(
            game,
            0,
            battlefield=[gh],
            hand=[_instant("Zap")],
            mana={ManaType.RED: 1},
        )
        gh.register_triggers(game)
        cast_spell(game, 0, "Zap")
        assert CardType.CREATURE not in gh.card_types

    def test_opponent_spell_does_not_buff(self):
        game = create_game()
        p0, p1 = game.players
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], mana={ManaType.COLORLESS: 5})
        set_board_state(
            game, 1, hand=[_instant("Zap")], mana={ManaType.RED: 1}
        )
        gh.register_triggers(game)
        _animate(game, p0, gh)
        cast_spell(game, 1, "Zap")
        assert gh.power == 2
