"""Tests for SOS 133 — Tackle Artist."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_133.card_impl import TackleArtist
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CheapTestInstant(Instant):
    """Simple instant used to exercise Opus triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


class FiveManaTestSorcery(Sorcery):
    """Simple sorcery used to exercise the five-mana Opus threshold."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Five-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)


class TestTackleArtistProperties:
    """Static card data should match the SOS 133 spec."""

    def test_is_orc_sorcerer_creature_with_trample(self) -> None:
        card = TackleArtist(owner=None)

        assert isinstance(card, Creature)
        assert "Orc" in card.subtypes
        assert "Sorcerer" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = TackleArtist(owner=None)

        assert card.name == "Tackle Artist"
        assert card.mana_cost == ManaCost.parse("{3}{R}")
        assert card.base_power == 4
        assert card.base_toughness == 3


class TestTackleArtistOpus:
    """Tackle Artist should reward instant and sorcery casts."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TackleArtist(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_an_instant_puts_one_plus_one_counter_on_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = TackleArtist(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert card.plus_one_counters == 1
        assert card.power == 5
        assert card.toughness == 4

    def test_five_or_more_mana_spell_puts_two_plus_one_counters_on_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = TackleArtist(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 5})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert card.plus_one_counters == 2
        assert card.power == 6
        assert card.toughness == 5

    def test_casting_a_creature_spell_does_not_trigger_opus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = TackleArtist(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Practice Performer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card], hand=[creature_spell], mana={ManaType.RED: 2})
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
