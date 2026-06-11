"""Tests for SOS 60 — Muse Seeker."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_60.card_impl import MuseSeeker
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CheapTestInstant(Instant):
    """Simple instant used to exercise Muse Seeker's Opus trigger."""

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


class TestMuseSeekerProperties:
    """Static card data should match the SOS 60 spec."""

    def test_is_elf_wizard_creature(self) -> None:
        card = MuseSeeker(owner=None)
        assert isinstance(card, Creature)
        assert "Elf" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = MuseSeeker(owner=None)
        assert card.name == "Muse Seeker"
        assert card.mana_cost == ManaCost.parse("{1}{U}")
        assert card.base_power == 1
        assert card.base_toughness == 2


class TestMuseSeekerOpus:
    """Muse Seeker should loot on small spells and only draw on larger ones."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MuseSeeker(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_small_instant_draws_a_card_then_discards_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = MuseSeeker(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)
        keep = CardImpl(name="Keep Studying", owner=p1, controller=p1)
        drawn_card = CardImpl(name="Fresh Insight", owner=p1, controller=p1)
        game.get_library(p1).add(drawn_card)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell, keep],
            mana={ManaType.BLUE: 1},
        )
        card.register_triggers(game)
        p1._script.append(drawn_card)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert game.get_hand(p1).contains(keep)
        assert not game.get_hand(p1).contains(drawn_card)
        assert game.get_graveyard(p1).contains(drawn_card)
        assert game.stack.peek().source is spell

    def test_casting_a_five_mana_sorcery_draws_a_card_without_discarding(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = MuseSeeker(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)
        drawn_card = CardImpl(name="Big Finish", owner=p1, controller=p1)
        game.get_library(p1).add(drawn_card)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 5},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert game.get_hand(p1).contains(drawn_card)
        assert not game.get_graveyard(p1).contains(drawn_card)
        assert game.stack.peek().source is spell

    def test_casting_a_noninstant_nonsorcery_spell_does_not_trigger_opus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = MuseSeeker(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Lecture Hall Cub",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{U}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[creature_spell],
            mana={ManaType.BLUE: 2},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
