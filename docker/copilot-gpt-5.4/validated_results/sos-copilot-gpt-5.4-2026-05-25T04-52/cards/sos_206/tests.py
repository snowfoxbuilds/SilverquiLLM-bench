"""Tests for SOS 206 — Nita, Forum Conciliator."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.cards.sos.sos_206.card_impl import NitaForumConciliator
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import ActivatedAbility, CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, Supertype, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class BorrowedLesson(Sorcery):
    """Simple sorcery used to exercise Nita's stolen-spell interactions."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Borrowed Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)


class PersonalLesson(Sorcery):
    """Simple sorcery used to prove Nita checks spell ownership."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Personal Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)


class TestNitaForumConciliatorProperties:
    """Static card data should match the SOS 206 spec."""

    def test_is_legendary_human_advisor_creature(self) -> None:
        card = NitaForumConciliator(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Human" in card.subtypes
        assert "Advisor" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = NitaForumConciliator(owner=None)

        assert card.name == "Nita, Forum Conciliator"
        assert card.mana_cost == ManaCost.parse("{1}{W}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestNitaForumConciliatorSpellCastTrigger:
    """Nita should reward you for casting spells you do not own."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NitaForumConciliator(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_spell_you_do_not_own_puts_a_counter_on_each_creature_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        nita = NitaForumConciliator(owner=p1, controller=p1)
        ally = Creature(
            name="Helpful Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        enemy = Creature(
            name="Opposing Student",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        borrowed = BorrowedLesson(owner=p2, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[nita, ally],
            hand=[borrowed],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        set_board_state(game, 1, battlefield=[enemy])
        borrowed.owner = p2
        borrowed.controller = p1
        nita.register_triggers(game)

        cast_spell_paid(game, p1, borrowed)

        assert len(game.stack) == 2
        assert game.stack.peek().source is nita

        resolve_top(game)

        assert nita.plus_one_counters == 1
        assert ally.plus_one_counters == 1
        assert enemy.plus_one_counters == 0

    def test_casting_a_spell_you_own_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        nita = NitaForumConciliator(owner=p1, controller=p1)
        ally = Creature(
            name="Helpful Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = PersonalLesson(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[nita, ally],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        nita.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert nita.plus_one_counters == 0
        assert ally.plus_one_counters == 0


class TestNitaForumConciliatorActivatedAbility:
    """Nita should steal opposing graveyard spells at sorcery speed."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = NitaForumConciliator(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_two_generic_mana_and_sacrificing_another_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        nita = NitaForumConciliator(owner=p1, controller=p1)
        fodder = Creature(
            name="Disposable Intern",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(
            game,
            0,
            battlefield=[nita, fodder],
            mana={ManaType.COLORLESS: 2},
        )
        p1._script.append(fodder)
        ability = nita.get_activated_abilities()[0]

        assert ability.cost(game, nita) is True
        assert game.get_battlefield(p1).contains(nita)
        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)
        assert p1.mana_pool.total() == 0

    def test_activation_cost_fails_without_another_creature_to_sacrifice(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        nita = NitaForumConciliator(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[nita], mana={ManaType.COLORLESS: 2})
        ability = nita.get_activated_abilities()[0]

        assert ability.cost(game, nita) is False
        assert game.get_battlefield(p1).contains(nita)
        assert p1.mana_pool.total() == 2

    def test_activation_cost_fails_outside_sorcery_speed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        nita = NitaForumConciliator(owner=p1, controller=p1)
        fodder = Creature(
            name="Disposable Intern",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(
            game,
            0,
            battlefield=[nita, fodder],
            mana={ManaType.COLORLESS: 2},
        )
        p1._script.append(fodder)
        ability = nita.get_activated_abilities()[0]

        assert ability.cost(game, nita) is False
        assert game.get_battlefield(p1).contains(nita)
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        assert p1.mana_pool.total() == 2

    def test_effect_exiles_a_target_opponents_instant_or_sorcery_and_permission_ends_this_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        nita = NitaForumConciliator(owner=p1, controller=p1)
        stolen = BorrowedLesson(owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[nita])
        set_board_state(game, 1, graveyard=[stolen])
        stolen.owner = p2
        stolen.controller = p2
        nita.chosen_targets = [stolen]
        ability = nita.get_activated_abilities()[0]

        ability.effect(game)

        assert game.get_exile(p2).contains(stolen)
        assert not game.get_graveyard(p2).contains(stolen)
        assert game.can_player_play_exiled_card(p1, stolen) is True
        assert game.can_player_play_exiled_card(p2, stolen) is False

        for _ in range(12):
            game.advance_phase()

        assert game.can_player_play_exiled_card(p1, stolen) is False

    def test_effect_does_not_exile_a_spell_card_from_your_own_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        nita = NitaForumConciliator(owner=p1, controller=p1)
        own_spell = BorrowedLesson(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[nita], graveyard=[own_spell])
        nita.chosen_targets = [own_spell]
        ability = nita.get_activated_abilities()[0]

        ability.effect(game)

        assert game.get_graveyard(p1).contains(own_spell)
        assert not game.get_exile(p1).contains(own_spell)
        assert game.can_player_play_exiled_card(p1, own_spell) is False

    def test_exiled_spell_can_be_cast_with_mana_of_any_type_and_is_exiled_after_it_resolves(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        nita = NitaForumConciliator(owner=p1, controller=p1)
        stolen = BorrowedLesson(owner=p2, controller=p2)
        set_board_state(
            game,
            0,
            battlefield=[nita],
            mana={ManaType.RED: 2},
        )
        set_board_state(game, 1, graveyard=[stolen])
        stolen.owner = p2
        stolen.controller = p2
        nita.chosen_targets = [stolen]
        ability = nita.get_activated_abilities()[0]

        ability.effect(game)
        cast_spell_paid(game, p1, stolen, from_zone=Zone.EXILE)

        assert len(game.stack) == 2
        assert game.stack.peek().source is nita

        resolve_top(game)
        resolve_top(game)

        assert game.get_exile(p2).contains(stolen)
        assert not game.get_graveyard(p2).contains(stolen)
