"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.types import CardType, ManaCost, ManaType
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


class TestLectureNote(Instant):
    """Simple instant used to verify spell-cast and restricted-mana behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Lecture Note")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class TestCampusResearcher(Creature):
    """Simple creature used to verify restricted mana and non-trigger cases."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Campus Researcher")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)


def _activate_mana_ability(game, source, ability_index: int) -> None:
    """Activate one of *source*'s mana abilities immediately."""
    ability = source.get_mana_abilities()[ability_index]
    activate_ability(
        game,
        source.controller,
        ActivatedAbilityInstance(
            source=source,
            controller=source.controller,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
            description=ability.description,
        ),
    )


def _activate_nonmana_ability_and_resolve(game, source, ability_index: int) -> None:
    """Activate one of *source*'s non-mana abilities and resolve it."""
    ability = source.get_activated_abilities()[ability_index]
    activate_ability(
        game,
        source.controller,
        ActivatedAbilityInstance(
            source=source,
            controller=source.controller,
            cost=ability.cost,
            effect=ability.effect,
            description=ability.description,
        ),
    )
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)


class TestGreatHallOfTheBiblioplexProperties:
    """Static surfaces should match the SOS 257 spec."""

    def test_is_a_colorless_land_with_expected_rules_text(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        assert card.colors == set()
        assert card.rules_text == (
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with \"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.\" It's still a land."
        )

    def test_exposes_two_mana_abilities_and_one_animation_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert len(card.get_mana_abilities()) == 2
        assert len(card.get_activated_abilities()) == 1


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The two mana abilities should produce the promised mana and costs."""

    def test_colorless_mana_ability_taps_and_adds_one_colorless(self) -> None:
        game = create_game()
        player = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=player, controller=player)

        set_board_state(game, 0, battlefield=[hall])
        _activate_mana_ability(game, hall, 0)

        assert hall.is_tapped is True
        assert player.mana_pool.get(ManaType.COLORLESS) == 1
        assert player.mana_pool.total() == 1

    def test_colored_mana_ability_pays_one_life_and_adds_the_chosen_color(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        player = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=player, controller=player)

        set_board_state(game, 0, battlefield=[hall], life=7)
        _activate_mana_ability(game, hall, 1)

        assert hall.is_tapped is True
        assert player.life == 6
        assert player.mana_pool.get(ManaType.BLUE) == 1
        assert player.mana_pool.total() == 1

    def test_restricted_mana_can_be_spent_to_cast_an_instant(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        player = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=player, controller=player)
        spell = TestLectureNote(owner=player, controller=player)

        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        _activate_mana_ability(game, hall, 1)
        cast_spell(game, 0, "Lecture Note")

        assert hall.is_tapped is True
        assert player.life == 19
        assert game.get_graveyard(player).contains(spell)
        assert not game.get_hand(player).contains(spell)
        assert player.mana_pool.total() == 0

    def test_restricted_mana_cannot_be_spent_to_cast_a_creature(self) -> None:
        game = create_game(scripts=([ManaType.BLUE], []))
        player = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=player, controller=player)
        creature = TestCampusResearcher(owner=player, controller=player)

        set_board_state(game, 0, battlefield=[hall], hand=[creature])
        _activate_mana_ability(game, hall, 1)

        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Campus Researcher")

        assert hall.is_tapped is True
        assert player.life == 19
        assert game.get_hand(player).contains(creature)
        assert not game.get_graveyard(player).contains(creature)


class TestGreatHallOfTheBiblioplexAnimation:
    """The animation ability should create a land creature with the printed trigger."""

    def test_animation_ability_turns_hall_into_a_two_four_wizard_land_creature(self) -> None:
        game = create_game()
        player = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        _activate_nonmana_ability_and_resolve(game, hall, 0)
        game.effect_manager.apply_all(game)

        assert hall.is_tapped is False
        assert player.mana_pool.total() == 0
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_casting_an_instant_while_animated_gives_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        player = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=player, controller=player)
        spell = TestLectureNote(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1},
        )
        _activate_nonmana_ability_and_resolve(game, hall, 0)
        hall.register_triggers(game)
        game.effect_manager.apply_all(game)

        cast_spell(game, 0, "Lecture Note")
        game.effect_manager.apply_all(game)

        assert game.get_graveyard(player).contains(spell)
        assert hall.power == 3
        assert hall.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert CardType.CREATURE in hall.card_types
        assert hall.power == 2
        assert hall.toughness == 4

    def test_casting_a_creature_while_animated_does_not_trigger_the_power_bonus(self) -> None:
        game = create_game()
        player = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=player, controller=player)
        creature = TestCampusResearcher(owner=player, controller=player)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[creature],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1},
        )
        _activate_nonmana_ability_and_resolve(game, hall, 0)
        hall.register_triggers(game)
        game.effect_manager.apply_all(game)

        cast_spell(game, 0, "Campus Researcher")
        game.effect_manager.apply_all(game)

        assert game.get_battlefield(player).contains(creature)
        assert hall.power == 2
        assert hall.toughness == 4
