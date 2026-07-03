"""Tests for SOS 30 — Restoration Seminar."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_30.card_impl import RestorationSeminar
from benchmarks.sos.workspace.engine.casting import (
    can_cast_paradigm_copy,
    cast_paradigm_copy,
    cast_spell as cast_spell_paid,
    get_scheduled_paradigm_cards,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestRestorationSeminarProperties:
    """Static card data should match the SOS 30 spec."""

    def test_is_lesson_sorcery(self) -> None:
        card = RestorationSeminar(owner=None)
        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = RestorationSeminar(owner=None)
        assert card.name == "Restoration Seminar"
        assert card.mana_cost == ManaCost.parse("{5}{W}{W}")


class TestRestorationSeminarTargeting:
    """Restoration Seminar should target a nonland permanent card in your graveyard."""

    def test_returns_single_graveyard_target_requirement(self) -> None:
        game = create_game()
        reqs = RestorationSeminar(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.GRAVEYARD

    def test_target_filter_accepts_nonland_permanent_cards_and_rejects_lands_and_nonpermanents(self) -> None:
        game = create_game()
        req = RestorationSeminar(owner=None).get_targets(game)[0]

        acceptable = Creature(
            name="Recovered Lecturer",
            mana_cost=ManaCost.parse("{6}"),
            base_power=4,
            base_toughness=4,
        )
        land = Land(name="Recovered Campus")
        nonpermanent = CardImpl(name="Lecture Notes")

        assert req.filter_fn(acceptable) is True
        assert req.filter_fn(land) is False
        assert req.filter_fn(nonpermanent) is False


class TestRestorationSeminarResolution:
    """Restoration Seminar should reanimate a nonland permanent and exile itself."""

    def test_on_resolve_returns_the_chosen_target_to_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Recovered Lecturer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{6}"),
            base_power=4,
            base_toughness=4,
        )
        game.get_graveyard(p1).add(target)

        card = RestorationSeminar(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert not game.get_graveyard(p1).contains(target)
        assert game.get_battlefield(p1).contains(target)

    def test_resolving_a_cast_exiles_the_spell_due_to_paradigm(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        target = Creature(
            name="Recovered Lecturer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{6}"),
            base_power=4,
            base_toughness=4,
        )
        spell = RestorationSeminar(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            graveyard=[target],
            mana={ManaType.WHITE: 7},
        )
        p1._script.append(target)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(target)
        assert game.get_battlefield(p1).contains(target)

    def test_first_resolution_schedules_the_exiled_spell_for_your_precombat_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        target = Creature(
            name="Recovered Lecturer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{6}"),
            base_power=4,
            base_toughness=4,
        )
        spell = RestorationSeminar(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            graveyard=[target],
            mana={ManaType.WHITE: 7},
        )
        p1._script.append(target)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert can_cast_paradigm_copy(game, p1, spell) is True

        game.phase = Phase.POSTCOMBAT_MAIN
        assert can_cast_paradigm_copy(game, p1, spell) is False

        game.phase = Phase.PRECOMBAT_MAIN
        game.active_player_index = 1
        assert can_cast_paradigm_copy(game, p1, spell) is False
        assert can_cast_paradigm_copy(game, p2, spell) is False

    def test_casting_a_paradigm_copy_keeps_the_source_exiled_and_available_for_later_first_main_phases(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        initial_target = Creature(
            name="Recovered Lecturer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{6}"),
            base_power=4,
            base_toughness=4,
        )
        later_target = Creature(
            name="Recovered Dean",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{5}"),
            base_power=3,
            base_toughness=4,
        )
        spell = RestorationSeminar(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            graveyard=[initial_target],
            mana={ManaType.WHITE: 7},
        )
        p1._script.append(initial_target)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        game.get_graveyard(p1).add(later_target)
        p1._script.append(later_target)

        stack_obj = cast_paradigm_copy(game, p1, spell)

        assert stack_obj.source is not spell
        assert stack_obj.source.name == spell.name
        assert getattr(stack_obj.source, "paradigm_source", None) is spell

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert not game.get_graveyard(p1).contains(later_target)
        assert game.get_battlefield(p1).contains(later_target)

        game.phase = Phase.POSTCOMBAT_MAIN
        assert can_cast_paradigm_copy(game, p1, spell) is False

        game.phase = Phase.PRECOMBAT_MAIN
        assert can_cast_paradigm_copy(game, p1, spell) is True
