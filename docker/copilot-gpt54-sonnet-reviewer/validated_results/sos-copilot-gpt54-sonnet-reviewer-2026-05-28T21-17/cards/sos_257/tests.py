"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Creature, Instant, Land, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the card spec."""

    def test_is_a_land(self) -> None:
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_has_no_mana_cost(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).mana_cost == ManaCost()

    def test_starts_as_only_a_land(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).card_types == {CardType.LAND}


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The land should provide colorless and life-payment mana abilities."""

    def test_has_a_tap_ability_that_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])

        for ability in hall.get_mana_abilities():
            hall.is_tapped = False
            p1.life = 20
            p1.mana_pool.empty()

            if not ability.cost(game, hall):
                continue
            ability.mana_produced(game)

            if (
                p1.life == 20
                and p1.mana_pool.get(ManaType.COLORLESS) == 1
                and p1.mana_pool.total() == 1
            ):
                assert hall.is_tapped is True
                return

        raise AssertionError("Great Hall should have a mana ability that adds {C}")

    def test_has_a_tap_and_pay_life_ability_that_adds_a_chosen_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])

        for ability in hall.get_mana_abilities():
            hall.is_tapped = False
            p1.life = 20
            p1.mana_pool.empty()
            p1._script.clear()  # type: ignore[attr-defined]
            p1._script.append(ManaType.BLUE)  # type: ignore[attr-defined]

            if not ability.cost(game, hall):
                continue
            ability.mana_produced(game)

            if p1.life == 19 and p1.mana_pool.get(ManaType.BLUE) == 1 and p1.mana_pool.total() == 1:
                assert hall.is_tapped is True
                return

        raise AssertionError(
            "Great Hall should have a mana ability that pays 1 life and adds a chosen color"
        )

    @staticmethod
    def _activate_restricted_mana_ability(game, hall: GreatHallOfTheBiblioplex, color: ManaType) -> None:
        controller = hall.controller
        assert controller is not None

        for ability in hall.get_mana_abilities():
            hall.is_tapped = False
            controller.life = 20
            controller.mana_pool.empty()

            if not ability.cost(game, hall):
                continue
            ability.mana_produced(game)

            if controller.life == 19 and controller.mana_pool.get(color) == 1:
                assert controller.mana_pool.total() == 1
                assert hall.is_tapped is True
                return

        raise AssertionError("Great Hall should have a restricted colored mana ability")

    def test_restricted_colored_mana_can_cast_a_sorcery(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        lesson = Sorcery(name="Annotated Thesis", mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[hall], hand=[lesson])

        self._activate_restricted_mana_ability(game, hall, ManaType.BLUE)
        cast_spell(game, 0, "Annotated Thesis")

        assert p1.zones[Zone.GRAVEYARD].contains(lesson)
        assert p1.mana_pool.total() == 0

    def test_restricted_colored_mana_cannot_cast_a_creature(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        student = Creature(
            name="Blue Student",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[hall], hand=[student])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        self._activate_restricted_mana_ability(game, hall, ManaType.BLUE)

        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, student)

        assert p1.zones[Zone.HAND].contains(student)
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.total() == 1


class TestGreatHallOfTheBiblioplexAnimation:
    """The activated ability should permanently animate the land."""

    @staticmethod
    def _activate_animation(game, hall: GreatHallOfTheBiblioplex) -> None:
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)
        game.effect_manager.apply_all(game)

    def test_five_mana_turns_it_into_a_two_four_wizard_creature_thats_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        self._activate_animation(game, hall)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4


class TestGreatHallOfTheBiblioplexSpellCastTrigger:
    """The animated land should pump itself when you cast an instant or sorcery."""

    @staticmethod
    def _animate_hall(game, hall: GreatHallOfTheBiblioplex) -> None:
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)
        game.effect_manager.apply_all(game)

    def test_casting_an_instant_after_animation_gives_it_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        lesson = Instant(name="Practice Lesson", mana_cost=ManaCost.parse("{U}"))

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[lesson],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1},
        )

        self._animate_hall(game, hall)
        assert hall.power == 2

        cast_spell(game, 0, "Practice Lesson")
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 2

    def test_reactivating_an_already_animated_hall_does_not_make_one_spell_grant_two_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        lesson = Instant(name="Practice Lesson", mana_cost=ManaCost.parse("{U}"))

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[lesson],
            mana={ManaType.COLORLESS: 10, ManaType.BLUE: 1},
        )

        self._animate_hall(game, hall)

        ability = hall.get_activated_abilities()[0]
        if ability.cost(game, hall):
            ability.effect(game)
            game.effect_manager.apply_all(game)

        cast_spell(game, 0, "Practice Lesson")
        game.effect_manager.apply_all(game)

        assert hall.power == 3
