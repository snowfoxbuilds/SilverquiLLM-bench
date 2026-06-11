"""Tests for SOS 190 — Fractal Tender."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_190.card_impl import FractalTender
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import CounterAddedTriggeredEvent, EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise Ward."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]


class FourManaTestSorcery(Sorcery):
    """Four-mana sorcery used to exercise Increment."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Four-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        super().__init__(**kwargs)


def _fractal_tokens(game: object, player: object) -> list[Creature]:
    return [
        permanent
        for permanent in game.get_battlefield(player).get_all()
        if getattr(permanent, "is_token", False)
    ]


class TestFractalTenderProperties:
    """Static card data should match the SOS 190 spec."""

    def test_is_elf_wizard_creature_with_ward_and_increment(self) -> None:
        card = FractalTender(owner=None)

        assert isinstance(card, Creature)
        assert "Elf" in card.subtypes
        assert "Wizard" in card.subtypes
        assert Keyword.WARD in card.keywords

    def test_name_cost_power_and_toughness(self) -> None:
        card = FractalTender(owner=None)

        assert card.name == "Fractal Tender"
        assert card.mana_cost == ManaCost.parse("{3}{G}{U}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestFractalTenderWard:
    """Fractal Tender should enforce Ward {2} against opposing targeted spells."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_pay_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = FractalTender(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 1})
        p2._script.append(card)

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "countered"
        assert game.get_graveyard(p2).contains(spell)
        assert game.stack.is_empty()


class TestFractalTenderTriggers:
    """Fractal Tender should grow from Increment and bloom at end step."""

    def test_casting_a_four_mana_spell_adds_a_plus_one_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FourManaTestSorcery(owner=p1, controller=p1)
        card = FractalTender(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={
                ManaType.COLORLESS: 2,
                ManaType.GREEN: 1,
                ManaType.BLUE: 1,
            },
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Four-Mana Test Sorcery")

        assert card.plus_one_counters == 1

    def test_any_end_step_after_a_counter_was_put_on_it_this_turn_creates_a_three_three_fractal(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = FractalTender(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        add_counter(game, card, "study")
        while not game.stack.is_empty():
            resolve_top(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p2))

        assert len(game.stack) == 1
        resolve_top(game)

        tokens = _fractal_tokens(game, p1)
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert "Fractal" in token.subtypes
        assert get_colors(token) == {Color.GREEN, Color.BLUE}
        assert token.plus_one_counters == 3
        assert token.power == 3
        assert token.toughness == 3

    def test_end_step_does_not_trigger_from_preexisting_counters_alone(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = FractalTender(owner=p1, controller=p1)
        card._counters["study"] = 1
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert game.stack.is_empty()
        assert _fractal_tokens(game, p1) == []
