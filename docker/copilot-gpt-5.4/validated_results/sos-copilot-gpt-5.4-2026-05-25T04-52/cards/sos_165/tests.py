"""Tests for SOS 165 — Topiary Lecturer."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_165.card_impl import TopiaryLecturer
from benchmarks.sos.workspace.engine.card import Creature, ManaAbility, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class TwoManaTestSorcery(Sorcery):
    """Two-mana sorcery used to exercise Increment thresholds."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Two-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)


class TestTopiaryLecturerProperties:
    """Static card data should match the SOS 165 spec."""

    def test_is_elf_druid_creature(self) -> None:
        card = TopiaryLecturer(owner=None)

        assert isinstance(card, Creature)
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = TopiaryLecturer(owner=None)

        assert card.name == "Topiary Lecturer"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.base_power == 1
        assert card.base_toughness == 2


class TestTopiaryLecturerIncrement:
    """Topiary Lecturer should grow from qualifying spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_two_mana_spell_adds_a_plus_one_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestSorcery(owner=p1, controller=p1)
        card = TopiaryLecturer(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Sorcery")

        assert card.plus_one_counters == 1
        assert card.power == 2
        assert card.toughness == 3

    def test_casting_a_two_mana_spell_does_not_trigger_increment_once_it_is_a_two_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestSorcery(owner=p1, controller=p1)
        card = TopiaryLecturer(owner=p1, controller=p1)
        card.plus_one_counters = 1
        card._base_plus_one_counters = 1
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Sorcery")

        assert card.plus_one_counters == 1
        assert card.power == 2
        assert card.toughness == 3


class TestTopiaryLecturerManaAbility:
    """Topiary Lecturer should tap for green equal to its power."""

    def test_has_a_single_mana_ability(self) -> None:
        abilities = TopiaryLecturer(owner=None).get_mana_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ManaAbility)

    def test_mana_ability_cost_taps_this_creature_and_cannot_be_paid_while_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert ability.cost(game, card) is False

    def test_mana_ability_adds_green_equal_to_current_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TopiaryLecturer(owner=p1, controller=p1)
        card.plus_one_counters = 2
        card._base_plus_one_counters = 2
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True

        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.GREEN) == 3
