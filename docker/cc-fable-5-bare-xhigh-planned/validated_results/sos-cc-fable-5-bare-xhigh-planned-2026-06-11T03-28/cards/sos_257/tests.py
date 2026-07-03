"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType
from test_utils import TestSetupError, create_game, set_board_state, cast_spell


def _activate_mana(game, player, land, index):
    """Activate a printed mana ability by index through the engine."""
    ability = land.get_mana_abilities()[index]
    activate_ability(game, player, ActivatedAbilityInstance(
        source=land, controller=player,
        cost=ability.cost, effect=ability.mana_produced,
        is_mana_ability=True,
    ))


def _activate_animation(game, p1, p2, land):
    """Activate the printed {5} ability and resolve it via priority."""
    ability = land.get_activated_abilities()[0]
    activate_ability(game, p1, ActivatedAbilityInstance(
        source=land, controller=p1, cost=ability.cost, effect=ability.effect,
    ))
    p1._script.extend(["pass"])
    p2._script.extend(["pass"])
    priority_loop(game)


def _setup(game):
    p1 = game.players[0]
    land = GreatHallOfTheBiblioplex(owner=p1)
    set_board_state(game, 0, battlefield=[land])
    return p1, land


class TestGreatHallProperties:
    def test_static_data(self) -> None:
        land = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(land, Land)
        assert land.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in land.card_types
        assert CardType.CREATURE not in land.card_types
        assert len(land.get_mana_abilities()) == 2
        assert len(land.get_activated_abilities()) == 1


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        _activate_mana(game, p1, land, 0)
        assert land.is_tapped
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_restricted_any_color_costs_a_life(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        p1._script.extend([ManaType.BLUE])
        _activate_mana(game, p1, land, 1)
        assert land.is_tapped
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_restricted_mana_casts_instant(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        spell = Instant(name="Probe", mana_cost=ManaCost.parse("{U}"))
        game.get_hand(p1).add(spell)
        spell.owner = spell.controller = p1
        p1._script.extend([ManaType.BLUE])
        _activate_mana(game, p1, land, 1)
        cast_spell(game, 0, "Probe")
        assert game.get_graveyard(p1).contains(spell)

    def test_restricted_mana_cannot_cast_creature(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        bear = Creature(name="Hand Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{G}"))
        game.get_hand(p1).add(bear)
        bear.owner = bear.controller = p1
        p1._script.extend([ManaType.GREEN])
        _activate_mana(game, p1, land, 1)
        try:
            cast_spell(game, 0, "Hand Bear")
            cast_ok = True
        except TestSetupError:
            cast_ok = False
        assert not cast_ok
        assert game.get_hand(p1).contains(bear)


class TestGreatHallAnimation:
    def test_five_generic_animates_to_2_4_wizard(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        _activate_animation(game, p1, p2, land)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2
        assert land.toughness == 4

    def test_animation_noop_if_already_creature(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 10)
        _activate_animation(game, p1, p2, land)
        triggers_after_first = len(game.trigger_manager.get_triggers_for_source(land))
        _activate_animation(game, p1, p2, land)
        assert land.power == 2 and land.toughness == 4
        # The pump trigger must not be registered twice.
        assert len(game.trigger_manager.get_triggers_for_source(land)) == triggers_after_first

    def test_pump_on_instant_cast_stacks_and_expires(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        _activate_animation(game, p1, p2, land)

        for i in range(2):
            spell = Instant(name=f"Probe {i}", mana_cost=ManaCost.parse("{U}"))
            game.get_hand(p1).add(spell)
            spell.owner = spell.controller = p1
            p1.mana_pool.add(ManaType.BLUE, 1)
            cast_spell(game, 0, f"Probe {i}")

        assert land.power == 4  # 2 base + 1 per instant cast
        assert land.toughness == 4

        # End-of-turn cleanup removes the until-EOT pumps (this mirrors the
        # effect-expiry portion of turn._do_cleanup_step).
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2

    def test_opponent_casts_do_not_pump(self) -> None:
        game = create_game()
        p1, land = _setup(game)
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        _activate_animation(game, p1, p2, land)
        spell = Instant(name="Opp Probe", mana_cost=ManaCost.parse("{U}"))
        game.get_hand(p2).add(spell)
        spell.owner = spell.controller = p2
        p2.mana_pool.add(ManaType.BLUE, 1)
        cast_spell(game, 1, "Opp Probe")
        assert land.power == 2
