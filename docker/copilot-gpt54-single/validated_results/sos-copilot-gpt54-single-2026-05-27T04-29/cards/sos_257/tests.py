"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.casting import CastingError, cast_spell, play_land
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


class TestGreatHallOfTheBiblioplexProperties:
    """Printed land characteristics should match the card spec."""

    def test_is_a_colorless_land_with_no_mana_cost(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert card.mana_cost == ManaCost()
        assert card.colors == set()
        assert CardType.LAND in card.card_types


class TestGreatHallOfTheBiblioplexManaAbilities:
    """Mana production should follow the printed activated abilities."""

    @staticmethod
    def _activate_mana_ability(game, player, source, ability_index: int) -> None:
        printed = source.get_mana_abilities()[ability_index]
        activate_ability(
            game,
            player,
            ActivatedAbilityInstance(
                source=source,
                controller=player,
                cost=printed.cost,
                effect=printed.mana_produced,
                is_mana_ability=True,
                description=printed.description,
            ),
        )

    @staticmethod
    def _set_main_phase(game) -> None:
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    def test_first_mana_ability_taps_and_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])

        self._activate_mana_ability(game, p1, hall, 0)

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_restricted_mana_ability_taps_pays_one_life_and_adds_the_chosen_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.choose = lambda _options, _description: ManaType.BLUE

        set_board_state(game, 0, battlefield=[hall], life=20)

        self._activate_mana_ability(game, p1, hall, 1)

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_restricted_mana_can_be_spent_to_cast_an_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        self._set_main_phase(game)

        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(
            name="Lecture Note",
            mana_cost=ManaCost.parse("{U}"),
            owner=p1,
            controller=p1,
        )
        p1.choose = lambda _options, _description: ManaType.BLUE

        set_board_state(game, 0, battlefield=[hall], hand=[spell], life=20)

        self._activate_mana_ability(game, p1, hall, 1)
        cast_spell(game, p1, spell)
        game.stack.pop().on_resolve(game)

        assert p1.life == 19
        assert game.get_graveyard(p1).contains(spell)

    def test_restricted_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        self._set_main_phase(game)

        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature = Creature(
            name="Curious Pupil",
            mana_cost=ManaCost.parse("{U}"),
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        p1.choose = lambda _options, _description: ManaType.BLUE

        set_board_state(game, 0, battlefield=[hall], hand=[creature], life=20)

        self._activate_mana_ability(game, p1, hall, 1)

        with pytest.raises(CastingError):
            cast_spell(game, p1, creature)


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana activation should animate the land and grant its trigger."""

    @staticmethod
    def _set_main_phase(game) -> None:
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    @staticmethod
    def _resolve_animation_ability(game, player, hall: GreatHallOfTheBiblioplex) -> None:
        printed = hall.get_activated_abilities()[0]
        activate_ability(
            game,
            player,
            ActivatedAbilityInstance(
                source=hall,
                controller=player,
                cost=printed.cost,
                effect=printed.effect,
                description=printed.description,
            ),
        )
        game.stack.pop().on_resolve(game)
        game.effect_manager.apply_all(game)

    @staticmethod
    def _play_hall(game, player, hall: GreatHallOfTheBiblioplex) -> None:
        TestGreatHallOfTheBiblioplexAnimation._set_main_phase(game)
        set_board_state(game, 0, hand=[hall])
        play_land(game, player, hall)

    def test_animation_turns_the_land_into_a_two_four_wizard_land_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        self._play_hall(game, p1, hall)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        self._resolve_animation_ability(game, p1, hall)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_before_animation_casting_an_instant_or_sorcery_does_not_create_a_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Lesson", owner=p1, controller=p1)

        self._play_hall(game, p1, hall)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                card=spell,
                player=p1,
                controller=p1,
            ),
        )

        assert len(game.stack) == 0

    def test_after_animation_your_instant_or_sorcery_spell_gives_the_hall_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Study Break", owner=p1, controller=p1)

        self._play_hall(game, p1, hall)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        self._resolve_animation_ability(game, p1, hall)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell,
                card=spell,
                player=p1,
                controller=p1,
            ),
        )
        assert len(game.stack) == 1

        game.stack.pop().on_resolve(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 3
        assert hall.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2
        assert hall.toughness == 4

    def test_after_animation_opponents_spells_do_not_trigger_the_bonus(self) -> None:
        game = create_game()
        p1, p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        opponent_spell = Sorcery(
            name="Other Student's Notes",
            mana_cost=ManaCost.parse("{U}"),
            owner=p2,
            controller=p2,
        )

        self._play_hall(game, p1, hall)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        self._resolve_animation_ability(game, p1, hall)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=opponent_spell,
                card=opponent_spell,
                player=p2,
                controller=p2,
            ),
        )
        game.effect_manager.apply_all(game)

        assert len(game.stack) == 0
        assert hall.power == 2

    def test_after_animation_non_instant_non_sorcery_spells_do_not_trigger_the_bonus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Campus Familiar",
            mana_cost=ManaCost.parse("{1}"),
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )

        self._play_hall(game, p1, hall)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        self._resolve_animation_ability(game, p1, hall)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=creature_spell,
                card=creature_spell,
                player=p1,
                controller=p1,
            ),
        )
        game.effect_manager.apply_all(game)

        assert len(game.stack) == 0
        assert hall.power == 2
