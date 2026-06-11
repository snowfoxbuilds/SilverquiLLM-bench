"""Tests for SOS 170 — Abigale, Poet Laureate // Heroic Stanza."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_170.card_impl import AbigalePoetLaureateHeroicStanza
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CheapTestCreature(Creature):
    """Creature spell used to exercise Abigale's cast trigger."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Creature")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)


class CheapTestInstant(Instant):
    """Noncreature spell used to confirm the trigger is creature-only."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)


class TestAbigalePoetLaureateHeroicStanzaProperties:
    """Static front-face data should match the SOS 170 spec."""

    def test_is_legendary_bird_bard_with_flying(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Bird" in card.subtypes
        assert "Bard" in card.subtypes
        assert Keyword.FLYING in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)

        assert card.name == "Abigale, Poet Laureate"
        assert card.mana_cost == ManaCost.parse("{1}{W}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestAbigalePoetLaureateHeroicStanzaPrepared:
    """Abigale should become prepared when you cast creature spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_creature_spell_prepares_abigale(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)
        creature_spell = CheapTestCreature(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[creature_spell],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert card.is_prepared is True

    def test_casting_a_noncreature_spell_does_not_prepare_abigale(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        resolve_top(game)
        assert game.get_graveyard(p1).contains(spell)
        assert Keyword.FLYING in card.keywords
        assert card.is_prepared is False

    def test_prepared_spell_copy_is_heroic_stanza_and_unprepares_the_card(self) -> None:
        game = create_game()
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p1 = game.players[0]
        card = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Heroic Stanza"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{1}{W/B}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="Abigale, Poet Laureate.*not prepared"):
            card.cast_prepared_spell_copy(game)
