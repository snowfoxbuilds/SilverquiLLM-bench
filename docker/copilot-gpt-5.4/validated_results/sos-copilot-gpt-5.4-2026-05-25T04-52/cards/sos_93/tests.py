"""Tests for SOS 93 — Postmortem Professor."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_93.card_impl import PostmortemProfessor
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Instant
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import (
    create_game,
    declare_attackers,
    declare_blockers,
    set_board_state,
)


class TestPostmortemProfessorProperties:
    """Static card data should match the SOS 93 spec."""

    def test_is_zombie_warlock_creature(self) -> None:
        card = PostmortemProfessor(owner=None)

        assert isinstance(card, Creature)
        assert "Zombie" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = PostmortemProfessor(owner=None)

        assert card.name == "Postmortem Professor"
        assert card.mana_cost == ManaCost.parse("{1}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_cannot_block(self) -> None:
        game = create_game()
        p1, p2 = game.players
        attacker = Creature(
            name="Aggressive Student",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        attacker.summoning_sick = False
        professor = PostmortemProfessor(owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[professor])

        declare_attackers(game, ["Aggressive Student"])
        declare_blockers(game, {"Aggressive Student": ["Postmortem Professor"]})

        assert professor not in game.combat_state.blockers
        assert game.combat_state.attacker_blockers[attacker] == []
        assert professor.is_blocking is False


class TestPostmortemProfessorAttackTrigger:
    """Postmortem Professor should drain on attacks."""

    def test_registers_an_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PostmortemProfessor(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_when_it_attacks_each_opponent_loses_one_life_and_you_gain_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PostmortemProfessor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert p1.life == 21
        assert game.players[1].life == 19


class TestPostmortemProfessorActivatedAbility:
    """Postmortem Professor should reanimate itself from the graveyard."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = PostmortemProfessor(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_fails_without_enough_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PostmortemProfessor(owner=p1, controller=p1)
        spell_card = Instant(name="Spent Lesson", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, graveyard=[card, spell_card])
        ability = card.get_activated_abilities()[0]
        p1.mana_pool.add(ManaType.BLACK, 1)

        assert ability.cost(game, card) is False
        assert p1.mana_pool.total() == 1
        assert game.get_graveyard(p1).contains(card)
        assert game.get_graveyard(p1).contains(spell_card)

    def test_activation_cost_fails_without_an_instant_or_sorcery_card_to_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PostmortemProfessor(owner=p1, controller=p1)
        filler_creature = Creature(
            name="Filler Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, graveyard=[card, filler_creature])
        ability = card.get_activated_abilities()[0]
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)

        assert ability.cost(game, card) is False
        assert p1.mana_pool.total() == 2
        assert game.get_graveyard(p1).contains(card)
        assert game.get_graveyard(p1).contains(filler_creature)

    def test_activation_cost_exiles_an_instant_or_sorcery_card_and_leaves_professor_in_your_graveyard_until_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PostmortemProfessor(owner=p1, controller=p1)
        spell_card = Instant(name="Spent Lesson", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, graveyard=[card, spell_card])
        ability = card.get_activated_abilities()[0]
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1._script.append(spell_card)

        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0
        assert game.get_exile(p1).contains(spell_card)
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_battlefield(p1).contains(card)

    def test_effect_returns_this_card_from_your_graveyard_to_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PostmortemProfessor(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        assert game.get_battlefield(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)
