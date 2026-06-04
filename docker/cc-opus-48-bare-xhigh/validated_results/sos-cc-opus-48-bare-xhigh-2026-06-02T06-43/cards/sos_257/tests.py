"""Tests for Great Hall of the Biblioplex (SOS 257)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Creature, Instant, Land
from engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
from engine.types import CardType, ManaType, Zone
from test_utils import card_colors, create_game, set_board_state


def _instant(name: str = "Bolt") -> Instant:
    return Instant(name=name)


def _creature(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _resolve_stack(game: Any) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


def _setup(scripts=None, mana=None, life=20):
    game = create_game(scripts=(scripts or [], []))
    p1 = game.players[0]
    hall = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[hall], mana=mana or {}, life=life)
    return game, p1, hall


class TestProperties:
    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types

    def test_name(self) -> None:
        assert (
            GreatHallOfTheBiblioplex(owner=None).name
            == "Great Hall of the Biblioplex"
        )

    def test_colorless(self) -> None:
        assert card_colors(GreatHallOfTheBiblioplex(owner=None)) == set()

    def test_starts_noncreature(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.is_creature is False
        assert CardType.CREATURE not in card.card_types

    def test_inert_power_toughness(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.power == 0
        assert card.toughness == 0

    def test_has_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert len(card.get_mana_abilities()) == 2

    def test_has_one_activated_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert len(card.get_activated_abilities()) == 1


class TestColorlessMana:
    def test_tap_adds_colorless(self) -> None:
        game, p1, hall = _setup()
        ability = hall.get_mana_abilities()[0]
        assert ability.cost(game, hall) is True
        assert hall.is_tapped is True
        ability.mana_produced(game)
        assert p1.mana_pool.total() == 1
        assert p1.mana_pool.can_pay  # sanity: pool not empty

    def test_cost_fails_when_tapped(self) -> None:
        game, p1, hall = _setup()
        hall.is_tapped = True
        ability = hall.get_mana_abilities()[0]
        assert ability.cost(game, hall) is False


class TestAnyColorMana:
    def test_pays_life_and_adds_chosen_color(self) -> None:
        game, p1, hall = _setup(scripts=[ManaType.BLUE], life=20)
        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        assert hall.is_tapped is True
        assert p1.life == 19
        ability.mana_produced(game)
        assert p1.mana_pool.total() == 1

    def test_cost_fails_when_tapped(self) -> None:
        game, p1, hall = _setup(life=20)
        hall.is_tapped = True
        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is False
        assert p1.life == 20  # no life paid

    def test_cost_fails_at_zero_life(self) -> None:
        game, p1, hall = _setup(life=0)
        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is False
        assert hall.is_tapped is False

    def test_invalid_choice_defaults_white(self) -> None:
        game, p1, hall = _setup(scripts=["not-a-color"], life=20)
        ability = hall.get_mana_abilities()[1]
        ability.cost(game, hall)
        ability.mana_produced(game)
        # Default fallback is white; pool still gains exactly one mana.
        assert p1.mana_pool.total() == 1


class TestActivateFive:
    def test_cost_fails_without_five_mana(self) -> None:
        game, p1, hall = _setup(mana={ManaType.COLORLESS: 4})
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is False
        assert hall.is_creature is False

    def test_cost_pays_five(self) -> None:
        game, p1, hall = _setup(mana={ManaType.COLORLESS: 5})
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        assert p1.mana_pool.total() == 0

    def test_cost_fails_if_already_creature(self) -> None:
        game, p1, hall = _setup(mana={ManaType.COLORLESS: 5})
        hall.animate(game)
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is False
        assert p1.mana_pool.total() == 5  # nothing paid

    def test_effect_animates(self) -> None:
        game, p1, hall = _setup(mana={ManaType.COLORLESS: 5})
        ability = hall.get_activated_abilities()[0]
        ability.cost(game, hall)
        ability.effect(game)
        assert hall.is_creature is True


class TestAnimate:
    def test_adds_creature_and_wizard(self) -> None:
        game, p1, hall = _setup()
        hall.animate(game)
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes

    def test_power_toughness_after_animate(self) -> None:
        game, p1, hall = _setup()
        hall.animate(game)
        assert hall.power == 2
        assert hall.toughness == 4

    def test_still_a_land(self) -> None:
        game, p1, hall = _setup()
        hall.animate(game)
        assert CardType.LAND in hall.card_types

    def test_registers_two_triggers(self) -> None:
        game, p1, hall = _setup()
        hall.animate(game)
        assert len(game.trigger_manager.get_triggers_for_source(hall)) == 2

    def test_idempotent(self) -> None:
        game, p1, hall = _setup()
        hall.animate(game)
        hall.animate(game)
        assert len(game.trigger_manager.get_triggers_for_source(hall)) == 2


class TestCastTrigger:
    def _animate(self):
        game, p1, hall = _setup()
        hall.animate(game)
        return game, p1, hall

    def test_pumps_on_instant_cast(self) -> None:
        game, p1, hall = self._animate()
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(card=_instant(), controller=p1),
        )
        _resolve_stack(game)
        assert hall.power == 3
        assert hall.toughness == 4  # only +1/+0

    def test_pumps_stack(self) -> None:
        game, p1, hall = self._animate()
        for _ in range(2):
            game.trigger_manager.fire_event(
                game,
                SpellCastTriggeredEvent(card=_instant(), controller=p1),
            )
            _resolve_stack(game)
        assert hall.power == 4

    def test_no_pump_for_opponent(self) -> None:
        game, p1, hall = self._animate()
        p2 = game.players[1]
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(card=_instant(), controller=p2),
        )
        _resolve_stack(game)
        assert hall.power == 2

    def test_no_pump_for_noninstant(self) -> None:
        game, p1, hall = self._animate()
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(card=_creature(), controller=p1),
        )
        _resolve_stack(game)
        assert hall.power == 2


class TestEndStepReset:
    def test_pump_resets_at_end_step(self) -> None:
        game, p1, hall = _setup()
        hall.animate(game)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(card=_instant(), controller=p1),
        )
        _resolve_stack(game)
        assert hall.power == 3
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        _resolve_stack(game)
        assert hall.power == 2
