"""Tests for Great Hall of the Biblioplex (SOS 257)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _land(p):
    return GreatHallOfTheBiblioplex(owner=p, controller=p)


class TestProperties:
    def test_static_data(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        assert card.power == 0
        assert card.toughness == 0
        assert card._animated is False

    def test_three_mana_abilities_shape(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2


class TestColorlessMana:
    def test_taps_and_adds_colorless(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        ab = land.get_mana_abilities()[0]
        assert ab.cost(game, land) is True
        assert land.is_tapped is True
        ab.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_fails_when_already_tapped(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        land.is_tapped = True
        ab = land.get_mana_abilities()[0]
        assert ab.cost(game, land) is False
        assert p1.mana_pool.total() == 0


class TestAnyColorMana:
    def test_taps_pays_life_and_adds_chosen_color(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        p1.life = 20
        ab = land.get_mana_abilities()[1]
        assert ab.cost(game, land) is True
        assert land.is_tapped is True
        assert p1.life == 19
        p1._script.append(ManaType.RED)
        ab.mana_produced(game)
        assert p1.mana_pool.get(ManaType.RED) == 1

    def test_fails_when_already_tapped(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        land.is_tapped = True
        ab = land.get_mana_abilities()[1]
        before = p1.life
        assert ab.cost(game, land) is False
        assert p1.life == before


class TestAnimate:
    def test_animate_method_makes_two_four_wizard_land(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        land.animate(game)
        assert land._animated is True
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2
        assert land.toughness == 4

    def test_activate_ability_pays_five_and_animates(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})
        ability = land.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=land, controller=p1,
            cost=ability.cost, effect=ability.effect)
        activate_ability(game, p1, instance)
        _resolve_stack(game)
        assert land._animated is True
        assert land.power == 2
        assert land.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_cost_unavailable_when_already_animated(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        land.animate(game)
        ability = land.get_activated_abilities()[0]
        assert ability.cost(game, land) is False

    def test_cost_unavailable_without_enough_mana(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 4})
        ability = land.get_activated_abilities()[0]
        assert ability.cost(game, land) is False
        assert land._animated is False

    def test_animate_is_idempotent(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        land.animate(game)
        land.animate(game)  # no double-registration / no error
        assert land.power == 2


class TestPump:
    def _animated(self, game, p1):
        land = _land(p1)
        land.animate(game)
        return land

    def test_instant_pumps_plus_one_power(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = self._animated(game, p1)
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=spell, card=spell,
                                          player=p1, controller=p1))
        _resolve_stack(game)
        assert land.power == 3
        assert land.toughness == 4

    def test_sorcery_pumps(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = self._animated(game, p1)
        spell = Sorcery(name="Divination", owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=spell, card=spell,
                                          player=p1, controller=p1))
        _resolve_stack(game)
        assert land.power == 3

    def test_creature_spell_does_not_pump(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = self._animated(game, p1)
        spell = Creature(name="Bear", base_power=2, base_toughness=2,
                         owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=spell, card=spell,
                                          player=p1, controller=p1))
        _resolve_stack(game)
        assert land.power == 2

    def test_opponent_spell_does_not_pump(self) -> None:
        game = create_game()
        p1, p2 = game.players
        land = self._animated(game, p1)
        spell = Instant(name="Bolt", owner=p2, controller=p2)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=spell, card=spell,
                                          player=p2, controller=p2))
        _resolve_stack(game)
        assert land.power == 2

    def test_two_spells_stack_pump(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = self._animated(game, p1)
        for _ in range(2):
            spell = Instant(name="Bolt", owner=p1, controller=p1)
            game.trigger_manager.fire_event(
                game, SpellCastTriggeredEvent(spell=spell, card=spell,
                                              player=p1, controller=p1))
            _resolve_stack(game)
        assert land.power == 4


class TestCleanupReset:
    def test_apply_all_wipes_pump_but_keeps_animation(self) -> None:
        game = create_game()
        p1, _ = game.players
        land = _land(p1)
        set_board_state(game, 0, battlefield=[land])
        land.animate(game)
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=spell, card=spell,
                                          player=p1, controller=p1))
        _resolve_stack(game)
        assert land.power == 3
        game.effect_manager.apply_all(game)
        assert land.power == 2  # pump wiped back to base 2/4
        assert CardType.CREATURE in land.card_types  # animation durable
        assert "Wizard" in land.subtypes
        assert CardType.LAND in land.card_types
