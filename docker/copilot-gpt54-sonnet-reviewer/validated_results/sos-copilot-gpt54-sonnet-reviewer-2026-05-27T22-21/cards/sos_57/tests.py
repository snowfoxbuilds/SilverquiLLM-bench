"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell, resolve_top
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state


class TrainingSpell(Sorcery):
    """Simple spell used as a counterspell target."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)
        self.times_resolved = 0

    def on_resolve(self, game) -> None:
        self.times_resolved += 1


class DiscountedTrainingSpell(Sorcery):
    """Spell whose actual mana spent is lower than its printed mana cost."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Discounted Training Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        super().__init__(**kwargs)
        self.times_resolved = 0

    def cost_reduction(self, game) -> int:
        return 2

    def on_resolve(self, game) -> None:
        self.times_resolved += 1


class AcademyWizard(Creature):
    """Simple Wizard permanent for the control check."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Academy Wizard")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt needs a spell target already on the stack."""

    @staticmethod
    def _set_precombat_main(game, active_player_index: int = 0) -> None:
        game.active_player_index = active_player_index
        game.priority_player_index = active_player_index
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    def test_cannot_be_cast_without_a_spell_on_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)
        self._set_precombat_main(game)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.BLUE: 2,
                ManaType.COLORLESS: 1,
            },
        )

        with pytest.raises(CastingError):
            cast_spell(game, p1, spell)

    def test_returns_single_stack_spell_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target_spell = TrainingSpell(owner=p1, controller=p1)
        self._set_precombat_main(game)
        set_board_state(game, 0, hand=[target_spell], mana={ManaType.COLORLESS: 2})

        cast_spell(game, p1, target_spell)
        target_stack = game.stack.peek()
        reqs = ManaSculpt(owner=p1, controller=p1).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert "spell" in reqs[0].description.lower()
        assert reqs[0].filter_fn(target_stack) is True


class TestManaSculptResolution:
    """Resolution should counter the target and schedule Wizard mana correctly."""

    @staticmethod
    def _set_precombat_main(game) -> None:
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    @staticmethod
    def _cast_target_then_mana_sculpt(game, target_spell, *, battlefield=None, mana=None):
        p1 = game.players[0]
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        TestManaSculptResolution._set_precombat_main(game)
        set_board_state(
            game,
            0,
            battlefield=battlefield or [],
            hand=[target_spell, mana_sculpt],
            mana=mana
            or {
                ManaType.BLUE: 2,
                ManaType.COLORLESS: 3,
            },
        )

        cast_spell(game, p1, target_spell)
        target_stack = game.stack.peek()
        p1.choose_target = lambda options, requirement: target_stack
        cast_spell(game, p1, mana_sculpt)
        resolve_top(game)
        return p1, mana_sculpt

    def test_resolution_counters_the_target_spell(self) -> None:
        game = create_game()
        target_spell = TrainingSpell()

        p1, _mana_sculpt = self._cast_target_then_mana_sculpt(game, target_spell)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(target_spell)
        assert target_spell.times_resolved == 0

    def test_controlling_a_wizard_does_not_add_colorless_immediately(self) -> None:
        game = create_game()
        wizard = AcademyWizard()
        target_spell = TrainingSpell()

        p1, _mana_sculpt = self._cast_target_then_mana_sculpt(
            game,
            target_spell,
            battlefield=[wizard],
        )

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_wizard_control_adds_colorless_at_your_next_main_phase(self) -> None:
        game = create_game()
        wizard = AcademyWizard()
        target_spell = TrainingSpell()

        p1, _mana_sculpt = self._cast_target_then_mana_sculpt(
            game,
            target_spell,
            battlefield=[wizard],
        )

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_without_a_wizard_no_colorless_is_added_at_your_next_main_phase(self) -> None:
        game = create_game()
        target_spell = TrainingSpell()

        p1, _mana_sculpt = self._cast_target_then_mana_sculpt(game, target_spell)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_delayed_colorless_uses_actual_mana_spent_not_printed_mana_cost(self) -> None:
        game = create_game()
        wizard = AcademyWizard()
        target_spell = DiscountedTrainingSpell()

        p1, _mana_sculpt = self._cast_target_then_mana_sculpt(
            game,
            target_spell,
            battlefield=[wizard],
            mana={
                ManaType.BLUE: 2,
                ManaType.COLORLESS: 4,
            },
        )

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
