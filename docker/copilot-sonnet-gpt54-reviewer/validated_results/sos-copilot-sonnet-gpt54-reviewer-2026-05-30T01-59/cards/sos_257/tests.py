"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_land(game: Any = None) -> GreatHallOfTheBiblioplex:
    if game is None:
        game = create_game()
    p1 = game.players[0]
    land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
    return land


# ---------------------------------------------------------------------------
# Identity tests
# ---------------------------------------------------------------------------

class TestCardIdentity:
    def test_name(self) -> None:
        land = _make_land()
        assert land.name == "Great Hall of the Biblioplex"

    def test_is_land_type(self) -> None:
        land = _make_land()
        assert CardType.LAND in land.card_types

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost (empty ManaCost)."""
        land = _make_land()
        assert land.mana_cost == ManaCost()

    def test_not_creature_initially(self) -> None:
        land = _make_land()
        assert CardType.CREATURE not in land.card_types


# ---------------------------------------------------------------------------
# Basic tap: {T} → Add {C}
# ---------------------------------------------------------------------------

class TestBasicTapManaAbility:
    def test_adds_colorless_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])

        before = p1.mana_pool.get(ManaType.COLORLESS)
        abilities = land.get_mana_abilities()
        tap_ability = abilities[0]
        tap_ability.cost(game, land)
        tap_ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == before + 1
        assert land.is_tapped is True

    def test_cannot_tap_twice(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])

        abilities = land.get_mana_abilities()
        tap_ability = abilities[0]
        tap_ability.cost(game, land)  # first tap
        result = tap_ability.cost(game, land)  # second attempt
        assert result is False


# ---------------------------------------------------------------------------
# Life tap: {T}, Pay 1 life → Add colored mana
# ---------------------------------------------------------------------------

class TestLifeTapManaAbility:
    def test_adds_colored_mana_and_costs_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], life=20)

        # Script GREEN as the color choice
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(ManaType.GREEN)

        abilities = land.get_mana_abilities()
        life_tap = abilities[1]
        cost_paid = life_tap.cost(game, land)
        assert cost_paid is True
        assert land.is_tapped is True
        assert p1.life == 19  # paid 1 life

        life_tap.mana_produced(game)
        # Should have added a colored mana (GREEN from script)
        assert p1.mana_pool.get(ManaType.GREEN) >= 1

    def test_cost_fails_if_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.is_tapped = True
        set_board_state(game, 0, battlefield=[land])

        abilities = land.get_mana_abilities()
        life_tap = abilities[1]
        result = life_tap.cost(game, land)
        assert result is False


# ---------------------------------------------------------------------------
# Animate ability: {5} → becomes 2/4 Wizard creature + land
# ---------------------------------------------------------------------------

class TestAnimateAbility:
    def test_becomes_creature_and_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        abilities = land.get_activated_abilities()
        assert len(abilities) == 1
        animate = abilities[0]

        cost_paid = animate.cost(game, land)
        assert cost_paid is True
        animate.effect(game)

        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types

    def test_power_toughness_is_2_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        animate = land.get_activated_abilities()[0]
        animate.cost(game, land)
        animate.effect(game)

        assert land.power == 2
        assert land.toughness == 4

    def test_wizard_subtype_added(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        animate = land.get_activated_abilities()[0]
        animate.cost(game, land)
        animate.effect(game)

        assert "Wizard" in land.subtypes

    def test_animate_fails_if_already_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.card_types.add(CardType.CREATURE)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        animate = land.get_activated_abilities()[0]
        result = animate.cost(game, land)
        assert result is False

    def test_animate_fails_without_enough_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 4})

        animate = land.get_activated_abilities()[0]
        result = animate.cost(game, land)
        assert result is False


# ---------------------------------------------------------------------------
# Animated creature trigger: +1/+0 per instant/sorcery cast
# ---------------------------------------------------------------------------

class TestAnimatedCreatureTrigger:
    def test_instant_cast_gives_plus1_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        # Animate the land
        animate = land.get_activated_abilities()[0]
        animate.cost(game, land)
        animate.effect(game)

        base_power = land.power
        assert base_power == 2

        # Create an instant card and cast it (triggering spell cast event)
        from engine.events import SpellCastTriggeredEvent
        fake_instant = Instant(owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=fake_instant, player=p1, card=fake_instant),
        )
        # Resolve any pending triggers
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        # Apply effects
        game.effect_manager.apply_all(game)

        assert land.power == base_power + 1

    def test_sorcery_cast_gives_plus1_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        animate = land.get_activated_abilities()[0]
        animate.cost(game, land)
        animate.effect(game)

        from engine.events import SpellCastTriggeredEvent
        fake_sorcery = Sorcery(owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=fake_sorcery, player=p1, card=fake_sorcery),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert land.power == 3

    def test_multiple_spells_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        animate = land.get_activated_abilities()[0]
        animate.cost(game, land)
        animate.effect(game)

        from engine.events import SpellCastTriggeredEvent
        for _ in range(3):
            fake_instant = Instant(owner=p1, controller=p1)
            game.trigger_manager.fire_event(
                game,
                SpellCastTriggeredEvent(spell=fake_instant, player=p1, card=fake_instant),
            )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert land.power == 5

    def test_opponent_spell_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        animate = land.get_activated_abilities()[0]
        animate.cost(game, land)
        animate.effect(game)

        from engine.events import SpellCastTriggeredEvent
        fake_instant = Instant(owner=p2, controller=p2)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=fake_instant, player=p2, card=fake_instant),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert land.power == 2  # no boost

    def test_trigger_resets_end_of_turn(self) -> None:
        """End-of-turn cleanup should remove the +1/+0 bonus."""
        from engine.types import Phase, Step
        from test_utils import advance_to_phase

        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})

        animate = land.get_activated_abilities()[0]
        animate.cost(game, land)
        animate.effect(game)

        from engine.events import SpellCastTriggeredEvent
        fake_instant = Instant(owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=fake_instant, player=p1, card=fake_instant),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert land.power == 3  # boosted

        # Cleanup removes end-of-turn effects
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2  # reset
