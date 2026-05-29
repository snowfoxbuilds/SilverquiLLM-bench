"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.casting import CastingError, cast_spell as cast_spell_to_stack, resolve_top
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


_COLORED_MANA = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


def _set_precombat_main(game, active_player_index: int = 0) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _mana_ability_instance(card, player, ability) -> ActivatedAbilityInstance:
    return ActivatedAbilityInstance(
        source=card,
        controller=player,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
        description=ability.description,
    )


def _activated_ability_instance(card, player, ability) -> ActivatedAbilityInstance:
    return ActivatedAbilityInstance(
        source=card,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        description=ability.description,
    )


def _fresh_hall_on_battlefield():
    game = create_game()
    p1 = game.players[0]
    hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
    set_board_state(game, 0, battlefield=[hall])
    _set_precombat_main(game)
    return game, p1, hall


def _activate_restricted_mana_ability(game, player, hall, chosen_color: ManaType) -> None:
    player.choose = lambda _options, _description, mt=chosen_color: mt  # type: ignore[method-assign]
    ability = hall.get_mana_abilities()[1]
    activate_ability(game, player, _mana_ability_instance(hall, player, ability))


def _animate_hall(game, player, hall) -> None:
    ability = hall.get_activated_abilities()[0]
    activate_ability(game, player, _activated_ability_instance(hall, player, ability))
    resolve_top(game)
    game.effect_manager.apply_all(game)


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_named_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in card.card_types

    def test_has_no_mana_cost(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).mana_cost == ManaCost()


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The land should provide its printed colorless and life-pay mana abilities."""

    def test_has_a_mana_ability_that_taps_for_colorless(self) -> None:
        game, p1, hall = _fresh_hall_on_battlefield()
        abilities = hall.get_mana_abilities()

        for ability in abilities:
            before_life = p1.life
            activate_ability(game, p1, _mana_ability_instance(hall, p1, ability))
            if p1.mana_pool.get(ManaType.COLORLESS) == 1:
                assert p1.mana_pool.total() == 1
                assert p1.life == before_life
                assert hall.is_tapped is True
                return

            hall.is_tapped = False
            p1.mana_pool.empty()

        raise AssertionError("expected one mana ability to add exactly one colorless mana")

    def test_has_a_life_payment_mana_ability_that_can_produce_any_color(self) -> None:
        for chosen_color in _COLORED_MANA:
            produced_requested_color = False

            for ability_index in range(len(GreatHallOfTheBiblioplex(owner=None).get_mana_abilities())):
                game, p1, hall = _fresh_hall_on_battlefield()
                p1.choose = lambda _options, _description, mt=chosen_color: mt  # type: ignore[method-assign]
                ability = hall.get_mana_abilities()[ability_index]
                before_life = p1.life

                activate_ability(game, p1, _mana_ability_instance(hall, p1, ability))

                if p1.mana_pool.get(chosen_color) == 1 and p1.mana_pool.total() == 1:
                    assert p1.life == before_life - 1
                    assert hall.is_tapped is True
                    produced_requested_color = True
                    break

            assert produced_requested_color, f"expected the land to be able to produce {chosen_color.name}"

    def test_restricted_colored_mana_can_be_spent_to_cast_an_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(
            name="Reference Note",
            mana_cost=ManaCost(pips={ManaType.BLUE: 1}),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        _set_precombat_main(game)

        _activate_restricted_mana_ability(game, p1, hall, ManaType.BLUE)
        cast_spell_to_stack(game, p1, spell)

        assert p1.mana_pool.total() == 0
        assert len(game.stack.objects()) == 1
        assert game.stack.objects()[0].source is spell

    def test_restricted_colored_mana_cannot_be_spent_to_cast_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Campus Student",
            mana_cost=ManaCost(pips={ManaType.BLUE: 1}),
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[hall], hand=[creature_spell])
        _set_precombat_main(game)

        _activate_restricted_mana_ability(game, p1, hall, ManaType.BLUE)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_to_stack(game, p1, creature_spell)

        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert game.get_hand(p1).contains(creature_spell)


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana activated ability should animate the land without removing land type."""

    def test_animation_ability_requires_five_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 4})
        _set_precombat_main(game)

        ability = hall.get_activated_abilities()[0]

        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, p1, _activated_ability_instance(hall, p1, ability))

        assert game.stack.is_empty()
        assert CardType.CREATURE not in hall.card_types

    def test_animation_turns_hall_into_a_two_four_wizard_land_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _set_precombat_main(game)

        _animate_hall(game, p1, hall)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.base_power == 2
        assert hall.base_toughness == 4


class TestGreatHallOfTheBiblioplexSpellcastTrigger:
    """The granted trigger should exist only after animation and buff only instants/sorceries."""

    def test_unanimated_hall_does_not_trigger_when_you_cast_an_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Reference Note", mana_cost=ManaCost(), owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack.objects()) == 1

    def test_animated_hall_gets_plus_one_power_until_end_of_turn_when_you_cast_an_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Reference Note", mana_cost=ManaCost(), owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[spell],
            mana={ManaType.COLORLESS: 5},
        )
        _set_precombat_main(game)

        _animate_hall(game, p1, hall)
        assert hall.power == 2

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack.objects()) == 2

        resolve_top(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 3
        assert hall.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2
        assert hall.toughness == 4

    def test_animated_hall_does_not_trigger_when_you_cast_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Campus Student",
            mana_cost=ManaCost(),
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 5},
        )
        _set_precombat_main(game)

        _animate_hall(game, p1, hall)
        cast_spell_to_stack(game, p1, creature_spell)

        assert len(game.stack.objects()) == 1
        game.effect_manager.apply_all(game)
        assert hall.power == 2
