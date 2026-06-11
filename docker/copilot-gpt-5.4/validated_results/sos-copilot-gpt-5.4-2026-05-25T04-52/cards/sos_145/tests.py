"""Tests for SOS 145 — Emeritus of Abundance // Regrowth."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_145.card_impl import EmeritusOfAbundanceRegrowth
from benchmarks.sos.workspace.engine.casting import CastingError, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, declare_attackers, set_board_state


class TestEmeritusOfAbundanceRegrowthProperties:
    """Static front-face data should match the SOS 145 spec."""

    def test_is_elf_druid_creature_with_vigilance(self) -> None:
        card = EmeritusOfAbundanceRegrowth(owner=None)

        assert isinstance(card, Creature)
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes
        assert Keyword.VIGILANCE in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = EmeritusOfAbundanceRegrowth(owner=None)

        assert card.name == "Emeritus of Abundance"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestEmeritusOfAbundanceRegrowthPrepared:
    """Emeritus of Abundance should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_regrowth_and_unprepares_the_card(self) -> None:
        game = create_game()
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p1 = game.players[0]
        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        graveyard_card = CardImpl(name="Useful Lesson", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[graveyard_card])
        p1._script.append(graveyard_card)
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Regrowth"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{1}{G}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)


class TestEmeritusOfAbundanceRegrowthAttackTrigger:
    """Attacking should re-prepare the creature only when you control eight lands."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attacking_with_eight_lands_puts_a_trigger_on_the_stack_and_prepares_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lands = [Land(name=f"Forest {idx}", owner=p1, controller=p1) for idx in range(8)]
        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card, *lands])
        card.become_unprepared()
        card.register_triggers(game)

        declare_attackers(game, ["Emeritus of Abundance"])

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.is_prepared is True

    def test_attacking_with_fewer_than_eight_lands_does_not_prepare_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lands = [Land(name=f"Forest {idx}", owner=p1, controller=p1) for idx in range(7)]
        card = EmeritusOfAbundanceRegrowth(owner=p1, controller=p1)
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card, *lands])
        card.become_unprepared()
        card.register_triggers(game)

        declare_attackers(game, ["Emeritus of Abundance"])

        assert game.stack.is_empty()
        assert card.is_prepared is False
