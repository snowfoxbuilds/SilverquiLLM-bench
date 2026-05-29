"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.casting import CastingError, cast_spell as engine_cast_spell, play_land
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import (
    advance_to_end_step_and_cleanup,
    advance_to_phase,
    create_game,
    set_board_state,
)


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land(self) -> None:
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_has_no_mana_cost(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).mana_cost == ManaCost()


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The land's two mana abilities should match the printed rules text."""

    @staticmethod
    def _play_hall(game):
        hall = GreatHallOfTheBiblioplex(owner=game.players[0], controller=game.players[0])
        set_board_state(game, 0, hand=[hall])
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        play_land(game, game.players[0], hall)
        return hall

    def test_first_mana_ability_taps_and_adds_colorless(self) -> None:
        game = create_game()
        hall = self._play_hall(game)
        p1 = game.players[0]

        ability = hall.get_mana_abilities()[0]

        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_second_mana_ability_taps_costs_life_and_adds_chosen_color(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        hall = self._play_hall(game)
        p1 = game.players[0]
        life_before = p1.life

        ability = hall.get_mana_abilities()[1]

        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        assert hall.is_tapped is True
        assert p1.life == life_before - 1
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_restricted_mana_can_cast_an_instant_spell(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        hall = self._play_hall(game)
        p1 = game.players[0]
        spell = Instant(
            name="Quick Study",
            mana_cost=ManaCost.parse("{U}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[spell])

        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        engine_cast_spell(game, p1, spell)
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.BLUE) == 0
        assert p1.mana_pool.get_tracked_mana() == []
        assert game.get_graveyard(p1).contains(spell) is True

    def test_restricted_mana_can_cast_a_sorcery_spell(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        hall = self._play_hall(game)
        p1 = game.players[0]
        spell = Sorcery(
            name="Campus Notes",
            mana_cost=ManaCost.parse("{U}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[spell])

        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        engine_cast_spell(game, p1, spell)
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.BLUE) == 0
        assert p1.mana_pool.get_tracked_mana() == []
        assert game.get_graveyard(p1).contains(spell) is True

    def test_restricted_mana_cannot_cast_a_creature_spell(self) -> None:
        game = create_game(scripts=([ManaType.GREEN], []))
        hall = self._play_hall(game)
        p1 = game.players[0]
        spell = Creature(
            name="Inkling Student",
            mana_cost=ManaCost.parse("{G}"),
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, hand=[spell])

        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, spell)

        assert game.get_hand(p1).contains(spell) is True
        assert p1.mana_pool.get(ManaType.GREEN) == 1
        assert len(p1.mana_pool.get_tracked_mana()) == 1

    def test_restricted_mana_cannot_pay_for_nonspell_activated_abilities(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        hall = self._play_hall(game)
        p1 = game.players[0]

        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)
        p1.mana_pool.add(ManaType.COLORLESS, 4)

        animate = hall.get_activated_abilities()[0]

        assert animate.cost(game, hall) is False
        assert CardType.CREATURE not in hall.card_types
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4


class TestGreatHallOfTheBiblioplexAnimation:
    """The {5} ability should animate the land and grant the spell-cast trigger."""

    @staticmethod
    def _play_hall(game):
        hall = GreatHallOfTheBiblioplex(owner=game.players[0], controller=game.players[0])
        set_board_state(game, 0, hand=[hall])
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        play_land(game, game.players[0], hall)
        return hall

    @staticmethod
    def _current_power(card) -> int | None:
        power = getattr(card, "power", None)
        if power is not None:
            return power
        power = getattr(card, "modified_power", None)
        if power is not None:
            return power
        return getattr(card, "base_power", None)

    @staticmethod
    def _current_toughness(card) -> int | None:
        toughness = getattr(card, "toughness", None)
        if toughness is not None:
            return toughness
        toughness = getattr(card, "modified_toughness", None)
        if toughness is not None:
            return toughness
        return getattr(card, "base_toughness", None)

    @staticmethod
    def _animate_hall(game, hall) -> None:
        controller = hall.controller
        assert controller is not None
        controller.mana_pool.add(ManaType.COLORLESS, 5)
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)

    @staticmethod
    def _spell_cast_event(controller, spell):
        return SpellCastTriggeredEvent(
            spell=spell,
            player=controller,
            card=spell,
            controller=controller,
        )

    def test_before_animation_casting_instant_or_sorcery_does_not_create_a_trigger(self) -> None:
        game = create_game()
        hall = self._play_hall(game)
        p1 = game.players[0]

        game.trigger_manager.fire_event(
            game,
            self._spell_cast_event(p1, Instant(name="Opt", owner=p1, controller=p1)),
        )

        assert game.stack.is_empty()

    def test_animation_ability_works_while_tapped_and_makes_hall_a_wizard_creature_land(self) -> None:
        game = create_game()
        hall = self._play_hall(game)

        hall.is_tapped = True
        self._animate_hall(game, hall)

        assert hall.is_tapped is True
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert self._current_power(hall) == 2
        assert self._current_toughness(hall) == 4

    def test_animated_hall_triggers_from_casting_an_instant_and_gets_plus_one_power(self) -> None:
        game = create_game()
        hall = self._play_hall(game)
        p1 = game.players[0]
        self._animate_hall(game, hall)
        power_before = self._current_power(hall)

        game.trigger_manager.fire_event(
            game,
            self._spell_cast_event(p1, Instant(name="Opt", owner=p1, controller=p1)),
        )

        assert len(game.stack.objects()) == 1
        trigger = game.stack.pop()
        trigger.on_resolve(game)
        assert self._current_power(hall) == power_before + 1

    def test_spell_cast_bonus_expires_at_cleanup_but_animation_remains(self) -> None:
        game = create_game()
        hall = self._play_hall(game)
        p1 = game.players[0]
        self._animate_hall(game, hall)

        game.trigger_manager.fire_event(
            game,
            self._spell_cast_event(p1, Instant(name="Opt", owner=p1, controller=p1)),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)
        assert self._current_power(hall) == 3

        advance_to_end_step_and_cleanup(game)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert self._current_power(hall) == 2
        assert self._current_toughness(hall) == 4

    def test_animated_hall_trigger_also_fires_for_sorcery_spells(self) -> None:
        game = create_game()
        hall = self._play_hall(game)
        p1 = game.players[0]
        self._animate_hall(game, hall)

        game.trigger_manager.fire_event(
            game,
            self._spell_cast_event(p1, Sorcery(name="Divination", owner=p1, controller=p1)),
        )

        assert len(game.stack.objects()) == 1

    def test_animated_hall_does_not_trigger_from_creature_spells(self) -> None:
        game = create_game()
        hall = self._play_hall(game)
        p1 = game.players[0]
        self._animate_hall(game, hall)

        game.trigger_manager.fire_event(
            game,
            self._spell_cast_event(
                p1,
                Creature(
                    name="Campus Adept",
                    owner=p1,
                    controller=p1,
                    base_power=2,
                    base_toughness=2,
                ),
            ),
        )

        assert game.stack.is_empty()

    def test_activating_the_animation_twice_does_not_create_duplicate_spell_cast_triggers(self) -> None:
        game = create_game()
        hall = self._play_hall(game)
        p1 = game.players[0]
        self._animate_hall(game, hall)
        self._animate_hall(game, hall)

        game.trigger_manager.fire_event(
            game,
            self._spell_cast_event(p1, Instant(name="Opt", owner=p1, controller=p1)),
        )

        assert len(game.stack.objects()) == 1
