"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state

ORACLE_TEXT = (
    "{T}: Add {C}.\n"
    "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast "
    "an instant or sorcery spell.\n"
    '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard creature with '
    '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until '
    'end of turn." It\'s still a land.'
)


class DummyInstant(Instant):
    """Simple instant used to trigger the Hall's magecraft-like ability."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Practice Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class DummySorcery(Sorcery):
    """Simple sorcery used to trigger the Hall's magecraft-like ability."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Lecture Notes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)


class DummyCreatureSpell(Creature):
    """Simple creature spell used to verify non-spells do not trigger the Hall."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Campus Assistant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


def _activate_animation_ability(game, player, hall) -> None:
    ability = hall.get_activated_abilities()[0]
    instance = ActivatedAbilityInstance(
        source=hall,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        description=ability.description,
    )
    activate_ability(game, player, instance)
    assert len(game.stack) == 1
    game.stack.pop().on_resolve(game)
    game.effect_manager.apply_all(game)


def _activate_restricted_mana_ability(game, hall) -> None:
    ability = next(
        ability
        for ability in hall.get_mana_abilities()
        if "Pay 1 life" in ability.description
    )
    assert ability.cost(game, hall) is True
    ability.mana_produced(game)


def _has_colorless_activation() -> bool:
    probe = GreatHallOfTheBiblioplex(owner=None)
    for index in range(len(probe.get_mana_abilities())):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])

        ability = hall.get_mana_abilities()[index]
        life_before = p1.life
        if not ability.cost(game, hall):
            continue
        ability.mana_produced(game)

        if (
            hall.is_tapped
            and p1.life == life_before
            and p1.mana_pool.get(ManaType.COLORLESS) == 1
            and p1.mana_pool.total() == 1
        ):
            return True
    return False


def _has_restricted_color_activation(target_color: ManaType) -> bool:
    probe = GreatHallOfTheBiblioplex(owner=None)
    for index in range(len(probe.get_mana_abilities())):
        game = create_game(scripts=([target_color], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])

        ability = hall.get_mana_abilities()[index]
        life_before = p1.life
        if not ability.cost(game, hall):
            continue
        ability.mana_produced(game)

        if (
            hall.is_tapped
            and p1.life == life_before - 1
            and p1.mana_pool.get(target_color) == 1
            and p1.mana_pool.total() == 1
        ):
            return True
    return False


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land_with_expected_rules_text_and_empty_mana_cost(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert card.mana_cost == ManaCost()
        assert card.rules_text == ORACLE_TEXT
        assert card.card_types == {CardType.LAND}


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The Hall should provide both colorless and life-paying colored mana."""

    def test_has_colorless_mana_ability_that_only_taps_for_one_colorless(self) -> None:
        assert _has_colorless_activation() is True

    def test_restricted_mana_ability_can_produce_each_color_and_costs_one_life(self) -> None:
        for mana_type in (
            ManaType.WHITE,
            ManaType.BLUE,
            ManaType.BLACK,
            ManaType.RED,
            ManaType.GREEN,
        ):
            assert _has_restricted_color_activation(mana_type) is True

    def test_restricted_mana_can_be_spent_to_cast_an_instant_spell(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = DummyInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], hand=[spell])

        _activate_restricted_mana_ability(game, hall)
        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 1
        assert not game.get_hand(p1).contains(spell)
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = DummyCreatureSpell(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], hand=[spell])

        _activate_restricted_mana_ability(game, hall)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, spell)

        assert game.get_hand(p1).contains(spell)
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_restricted_mana_cannot_pay_for_the_halls_animation_ability(self) -> None:
        game = create_game(scripts=([ManaType.WHITE], []))
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 4})

        _activate_restricted_mana_ability(game, hall)

        ability = hall.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=ability.cost,
            effect=ability.effect,
            description=ability.description,
        )

        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, p1, instance)

        assert CardType.CREATURE not in hall.card_types
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4
        assert p1.mana_pool.get(ManaType.WHITE) == 1


class TestGreatHallOfTheBiblioplexAnimation:
    """Animating the Hall should grant the printed creature form and trigger."""

    def test_animation_turns_hall_into_two_four_wizard_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        _activate_animation_ability(game, p1, hall)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert getattr(hall, "power", None) == 2
        assert getattr(hall, "toughness", None) == 4

    def test_unanimated_hall_does_not_trigger_when_you_cast_an_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = DummyInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], hand=[spell], mana={ManaType.BLUE: 1})
        hall.register_triggers(game)

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 1

    def test_animated_hall_gets_plus_one_zero_without_buffing_other_creatures_when_you_cast_an_instant(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        other_creature = Creature(
            name="Study Buddy",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = DummyInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall, other_creature],
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2

        game.stack.pop().on_resolve(game)
        game.effect_manager.apply_all(game)

        assert getattr(hall, "power", None) == 3
        assert getattr(hall, "toughness", None) == 4
        assert other_creature.power == 2
        assert other_creature.toughness == 2

    def test_animated_hall_triggers_from_your_sorcery_spell_and_buff_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = DummySorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2

        game.stack.pop().on_resolve(game)
        game.effect_manager.apply_all(game)
        assert getattr(hall, "power", None) == 3
        assert getattr(hall, "toughness", None) == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert getattr(hall, "power", None) == 2
        assert getattr(hall, "toughness", None) == 4
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types

    def test_animated_hall_does_not_trigger_from_creature_spells_or_opponents_instants(self) -> None:
        game = create_game()
        p1, p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = DummyCreatureSpell(owner=p1, controller=p1)
        opposing_instant = DummyInstant(owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, hand=[opposing_instant], mana={ManaType.BLUE: 1})
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)

        engine_cast_spell(game, p1, creature_spell)
        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)

        engine_cast_spell(game, p2, opposing_instant)
        assert len(game.stack) == 1

    def test_animating_an_already_animated_hall_does_not_create_duplicate_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = DummyInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[spell],
            mana={ManaType.COLORLESS: 10, ManaType.BLUE: 1},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        _activate_animation_ability(game, p1, hall)
        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2
