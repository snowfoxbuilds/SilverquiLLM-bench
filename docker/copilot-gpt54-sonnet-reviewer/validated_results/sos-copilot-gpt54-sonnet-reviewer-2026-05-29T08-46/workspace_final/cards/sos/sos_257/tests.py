"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.card import Creature, Instant, Land
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase
from test_utils import cast_spell, create_game, set_board_state


class SeminarNotes(Instant):
    """Simple one-mana instant used to test the Hall's restricted mana."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Seminar Notes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)


class ResearchAssistant(Creature):
    """Simple one-mana creature used to test mana-spending restrictions."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Research Assistant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)


def _resolve_entire_stack(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


def _restricted_mana_ability(hall):
    abilities = hall.get_mana_abilities()
    for ability in abilities:
        description = getattr(ability, "description", "")
        if "Pay 1 life" in description or "instant or sorcery" in description:
            return ability

    non_colorless = [
        ability
        for ability in abilities
        if "{C}" not in getattr(ability, "description", "")
    ]
    assert non_colorless, "Expected Great Hall to expose a restricted colored-mana ability"
    return non_colorless[0]


def _colorless_mana_ability(hall):
    abilities = hall.get_mana_abilities()
    for ability in abilities:
        if "{C}" in getattr(ability, "description", ""):
            return ability
    raise AssertionError("Expected Great Hall to expose a {T}: Add {C}. ability")


def _animation_ability(hall):
    abilities = hall.get_activated_abilities()
    for ability in abilities:
        description = getattr(ability, "description", "")
        if "2/4 Wizard creature" in description or "Wizard creature" in description:
            return ability
    assert len(abilities) == 1, "Expected exactly one non-mana activated ability"
    return abilities[0]


def _activate_mana_ability(game, player, hall, mana_ability) -> None:
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=hall,
            controller=player,
            cost=mana_ability.cost,
            effect=mana_ability.mana_produced,
            is_mana_ability=True,
            description=getattr(mana_ability, "description", ""),
        ),
    )


def _activate_animation(game, player, hall) -> None:
    ability = _animation_ability(hall)
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=hall,
            controller=player,
            cost=ability.cost,
            effect=ability.effect,
            description=getattr(ability, "description", ""),
        ),
    )
    _resolve_entire_stack(game)
    game.effect_manager.apply_all(game)


def _fire_spell_cast(game, spell, player) -> None:
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(
            spell=spell,
            card=spell,
            player=player,
            controller=player,
        ),
    )


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_a_land_named_great_hall_with_no_mana_cost(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert card.name == "Great Hall of the Biblioplex"
        assert card.mana_cost == ManaCost()
        assert card.colors == set()

    def test_starts_as_a_noncreature_land_with_no_keywords(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert CardType.CREATURE not in card.card_types
        assert card.keywords == Keyword(0)


class TestGreatHallOfTheBiblioplexManaAbilities:
    """Great Hall should provide both its colorless and restricted colored mana abilities."""

    def test_colorless_mana_ability_taps_and_adds_one_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])

        _activate_mana_ability(game, p1, hall, _colorless_mana_ability(hall))

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_restricted_mana_ability_costs_one_life_and_adds_one_colored_mana(self) -> None:
        game = create_game(player1_life=20)
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        colored_types = (
            ManaType.WHITE,
            ManaType.BLUE,
            ManaType.BLACK,
            ManaType.RED,
            ManaType.GREEN,
        )

        set_board_state(game, 0, battlefield=[hall])
        p1.choose = lambda options, description: options[0]

        _activate_mana_ability(game, p1, hall, _restricted_mana_ability(hall))

        assert hall.is_tapped is True
        assert p1.life == 19
        assert sum(p1.mana_pool.get(mana_type) for mana_type in colored_types) == 1
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_restricted_mana_can_cast_an_instant_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = SeminarNotes()

        set_board_state(game, 0, battlefield=[hall], hand=[spell], mana={})
        p1.choose = lambda options, description: options[0]

        _activate_mana_ability(game, p1, hall, _restricted_mana_ability(hall))
        cast_spell(game, 0, "Seminar Notes")

        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_hand(p1).contains(spell)
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_cannot_cast_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = ResearchAssistant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], hand=[creature_spell], mana={})
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        p1.choose = lambda options, description: options[0]

        _activate_mana_ability(game, p1, hall, _restricted_mana_ability(hall))

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, creature_spell)

        assert game.get_hand(p1).contains(creature_spell)
        assert not game.get_battlefield(p1).contains(creature_spell)


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana ability should animate the land and grant the printed spell-cast trigger."""

    def test_animation_ability_turns_it_into_a_two_four_wizard_land_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _activate_animation(game, p1, hall)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_animated_hall_gets_plus_one_power_until_end_of_turn_when_you_cast_an_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = SeminarNotes(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _activate_animation(game, p1, hall)
        _fire_spell_cast(game, spell, p1)

        assert len(game.stack) == 1

        _resolve_entire_stack(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 2
        assert hall.toughness == 4

    def test_creature_spells_do_not_trigger_the_animated_hall(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = ResearchAssistant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _activate_animation(game, p1, hall)
        _fire_spell_cast(game, creature_spell, p1)

        assert game.stack.is_empty()

    def test_opponents_instant_or_sorcery_spells_do_not_trigger_the_animated_hall(self) -> None:
        game = create_game()
        p1, p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        opponent_spell = SeminarNotes(owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _activate_animation(game, p1, hall)
        _fire_spell_cast(game, opponent_spell, p2)

        assert game.stack.is_empty()

    def test_activating_animation_again_while_already_a_creature_does_not_duplicate_the_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = SeminarNotes(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 10},
        )

        _activate_animation(game, p1, hall)
        _activate_animation(game, p1, hall)
        _fire_spell_cast(game, spell, p1)

        assert len(game.stack) == 1

        _resolve_entire_stack(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4
