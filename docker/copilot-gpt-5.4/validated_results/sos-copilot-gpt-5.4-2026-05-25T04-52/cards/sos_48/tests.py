"""Tests for SOS 48 — Exhibition Tidecaller."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_48 import card_impl as sos_48_card_impl
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state

ExhibitionTidecaller = getattr(sos_48_card_impl, "ExhibitionTidecaller", None)
if ExhibitionTidecaller is None:
    ExhibitionTidecaller = getattr(sos_48_card_impl, "FlowState")


class CheapTestInstant(Instant):
    """Simple instant used to exercise Opus triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class FiveManaTestSorcery(Sorcery):
    """Simple sorcery used to exercise the five-mana Opus threshold."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Five-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)


class TestExhibitionTidecallerProperties:
    """Static card data should match the SOS 48 spec."""

    def test_is_djinn_wizard_creature(self) -> None:
        card = ExhibitionTidecaller(owner=None)
        assert isinstance(card, Creature)
        assert "Djinn" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = ExhibitionTidecaller(owner=None)
        assert card.name == "Exhibition Tidecaller"
        assert card.mana_cost == ManaCost.parse("{U}")
        assert card.base_power == 0
        assert card.base_toughness == 2


class TestExhibitionTidecallerOpus:
    """Exhibition Tidecaller should mill a targeted player when you cast an instant or sorcery."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ExhibitionTidecaller(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_an_instant_mills_three_cards_from_the_chosen_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ExhibitionTidecaller(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)
        milled_cards = [CardImpl(name=f"Lesson {idx}", owner=p2, controller=p2) for idx in range(4)]
        for library_card in milled_cards:
            game.get_library(p2).add(library_card)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.BLUE: 1})
        card.register_triggers(game)
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert len(game.get_graveyard(p2).get_all()) == 3
        assert len(game.get_library(p2).get_all()) == 1
        assert game.get_library(p2).get_all()[0] is milled_cards[0]

    def test_casting_a_five_mana_sorcery_mills_ten_cards_instead(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ExhibitionTidecaller(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)
        milled_cards = [CardImpl(name=f"Lesson {idx}", owner=p2, controller=p2) for idx in range(11)]
        for library_card in milled_cards:
            game.get_library(p2).add(library_card)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.BLUE: 5})
        card.register_triggers(game)
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert len(game.get_graveyard(p2).get_all()) == 10
        assert len(game.get_library(p2).get_all()) == 1
        assert game.get_library(p2).get_all()[0] is milled_cards[0]

    def test_casting_a_noninstant_nonsorcery_spell_does_not_trigger_opus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ExhibitionTidecaller(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Lecture Hall Cub",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card], hand=[creature_spell], mana={ManaType.BLUE: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
