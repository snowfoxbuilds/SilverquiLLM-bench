"""Tests for SOS 44 — Echocasting Symposium."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_44.card_impl import EchocastingSymposium
from benchmarks.sos.workspace.engine.casting import (
    can_cast_paradigm_copy,
    cast_paradigm_copy,
    cast_spell as cast_spell_paid,
    get_scheduled_paradigm_cards,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEchocastingSymposiumProperties:
    """Static card data should match the SOS 44 spec."""

    def test_is_lesson_sorcery(self) -> None:
        card = EchocastingSymposium(owner=None)
        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = EchocastingSymposium(owner=None)
        assert card.name == "Echocasting Symposium"
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")


class TestEchocastingSymposiumTargeting:
    """Echocasting Symposium should target a player and a creature you control."""

    def test_returns_player_then_creature_target_requirements(self) -> None:
        game = create_game()
        reqs = EchocastingSymposium(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD

    def test_target_filters_accept_players_then_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = EchocastingSymposium(owner=p1, controller=p1)
        reqs = spell.get_targets(game)
        friendly_creature = Creature(
            name="Friendly Lecturer",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_creature = Creature(
            name="Opposing Lecturer",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        assert reqs[0].filter_fn(p1) is True
        assert reqs[0].filter_fn(p2) is True
        assert reqs[0].filter_fn(friendly_creature) is False
        assert reqs[1].filter_fn(friendly_creature) is True
        assert reqs[1].filter_fn(opposing_creature) is False
        assert reqs[1].filter_fn(p1) is False


class TestEchocastingSymposiumResolution:
    """Echocasting Symposium should copy a creature as a token for the target player."""

    def test_on_resolve_target_player_creates_a_token_copy_of_target_creature_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        source_creature = Creature(
            name="Lecture Adept",
            owner=p1,
            controller=p1,
            subtypes={"Human", "Wizard"},
            keywords=Keyword.FLYING,
            base_power=3,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(source_creature)
        card = EchocastingSymposium(owner=p1, controller=p1)
        card.chosen_targets = [p2, source_creature]

        card.on_resolve(game)

        tokens = game.get_battlefield(p2).get_all()
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert token.name == "Lecture Adept"
        assert token.power == 3
        assert token.toughness == 2
        assert "Human" in token.subtypes
        assert "Wizard" in token.subtypes
        assert Keyword.FLYING in token.keywords

    def test_paid_cast_exiles_itself_and_schedules_future_paradigm_copies(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        source_creature = Creature(
            name="Lecture Adept",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=2,
        )
        spell = EchocastingSymposium(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[source_creature],
            hand=[spell],
            mana={ManaType.BLUE: 6},
        )
        p1._script.extend([p2, source_creature])

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert can_cast_paradigm_copy(game, p1, spell) is True

        tokens = game.get_battlefield(p2).get_all()
        assert len(tokens) == 1
        assert tokens[0].is_token is True
        assert tokens[0].name == "Lecture Adept"

    def test_casting_a_paradigm_copy_keeps_the_source_exiled_and_creates_another_copy_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        source_creature = Creature(
            name="Lecture Adept",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=2,
        )
        spell = EchocastingSymposium(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[source_creature],
            hand=[spell],
            mana={ManaType.BLUE: 6},
        )
        p1._script.extend([p2, source_creature])
        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        p1._script.extend([p1, source_creature])
        stack_obj = cast_paradigm_copy(game, p1, spell)

        assert stack_obj.source is not spell
        assert getattr(stack_obj.source, "paradigm_source", None) is spell

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        permanents = game.get_battlefield(p1).get_all()
        assert len(permanents) == 2
        copied_tokens = [permanent for permanent in permanents if getattr(permanent, "is_token", False)]
        assert len(copied_tokens) == 1
        assert copied_tokens[0].name == "Lecture Adept"
