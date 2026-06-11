"""Tests for SOS 140 — Ambitious Augmenter."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_140.card_impl import AmbitiousAugmenter
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class TwoManaTestSorcery(Sorcery):
    """Two-mana sorcery used to exercise Increment."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Two-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)


class TestAmbitiousAugmenterProperties:
    """Static card data should match the SOS 140 spec."""

    def test_is_turtle_wizard_creature(self) -> None:
        card = AmbitiousAugmenter(owner=None)
        assert isinstance(card, Creature)
        assert "Turtle" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = AmbitiousAugmenter(owner=None)
        assert card.name == "Ambitious Augmenter"
        assert card.mana_cost == ManaCost.parse("{G}")
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestAmbitiousAugmenterIncrement:
    """Ambitious Augmenter should grow from qualifying spells."""

    def test_casting_a_two_mana_spell_adds_a_plus_one_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestSorcery(owner=p1, controller=p1)
        card = AmbitiousAugmenter(owner=p1, controller=p1)
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

    def test_casting_a_two_mana_spell_does_not_trigger_increment_once_it_is_a_two_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestSorcery(owner=p1, controller=p1)
        card = AmbitiousAugmenter(owner=p1, controller=p1)
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


class TestAmbitiousAugmenterDeathTrigger:
    """Ambitious Augmenter should replace itself with a Fractal when it dies with counters."""

    def test_registers_a_creature_dies_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AmbitiousAugmenter(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 2
        assert any(trigger.event_type is CreatureDiesTriggeredEvent for trigger in triggers)

    def test_when_it_dies_with_counters_it_creates_a_green_and_blue_fractal_token_and_puts_its_counters_on_that_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AmbitiousAugmenter(owner=p1, controller=p1)
        card.plus_one_counters = 2
        card._base_plus_one_counters = 2
        card._counters["study"] = 1
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        destroy(game, card)

        assert len(game.stack) == 1
        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert "Fractal" in token.subtypes
        assert get_colors(token) == {Color.GREEN, Color.BLUE}
        assert token.plus_one_counters == 2
        assert token.power == 2
        assert token.toughness == 2
        assert token.counters.get("study") == 1

    def test_when_it_dies_without_counters_it_does_not_create_a_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AmbitiousAugmenter(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        destroy(game, card)

        assert game.stack.is_empty()
        assert game.get_battlefield(p1).get_all() == []
