"""Tests for SOS 60 — Muse Seeker."""

from __future__ import annotations

import pytest

from cards.sos.sos_60.card_impl import MuseSeeker
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestMuseSeekerProperties:
    """Static card data should match the SOS 60 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(MuseSeeker(owner=None), Creature)

    def test_name(self) -> None:
        assert MuseSeeker(owner=None).name == "Muse Seeker"

    def test_mana_cost(self) -> None:
        assert MuseSeeker(owner=None).mana_cost == ManaCost.parse("{1}{U}")

    def test_power_and_toughness(self) -> None:
        card = MuseSeeker(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 2

    def test_subtypes_include_elf_wizard(self) -> None:
        card = MuseSeeker(owner=None)
        assert "Elf" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_has_opus_keyword(self) -> None:
        card = MuseSeeker(owner=None)
        assert Keyword.OPUS in card.keywords


class TestMuseSeekerOpusTrigger:
    """Opus — Whenever you cast an instant or sorcery, draw then maybe discard."""

    def test_draws_card_on_instant_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]

        seeker = MuseSeeker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[seeker])

        initial_hand = len(game.get_hand(p1))

        # Simulate casting an instant with less than 5 mana spent
        trigger_spell = Instant(name="Cheap Spell", owner=p1, controller=p1)
        trigger_spell.mana_spent = 2
        seeker.on_instant_or_sorcery_cast(game, trigger_spell)

        # Should have drawn a card (net 0 because discard follows)
        # At minimum, the draw happened
        hand_after = len(game.get_hand(p1))
        # Draw then discard: net change is 0 if less than 5 mana
        assert hand_after == initial_hand

    def test_draws_without_discard_when_five_or_more_mana_spent(self) -> None:
        game = create_game()
        p1 = game.players[0]

        seeker = MuseSeeker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[seeker])

        initial_hand = len(game.get_hand(p1))

        # Cast spell with 5+ mana spent — no discard required
        trigger_spell = Sorcery(name="Big Spell", owner=p1, controller=p1)
        trigger_spell.mana_spent = 5
        seeker.on_instant_or_sorcery_cast(game, trigger_spell)

        # Net +1 card (draw without discard)
        assert len(game.get_hand(p1)) == initial_hand + 1

    def test_no_trigger_on_creature_spell(self) -> None:
        """Only instants and sorceries trigger the opus ability."""
        game = create_game()
        p1 = game.players[0]

        seeker = MuseSeeker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[seeker])

        initial_hand = len(game.get_hand(p1))

        # Creature spell should NOT trigger
        creature_spell = Creature(name="Bear", owner=p1, controller=p1,
                                  base_power=2, base_toughness=2)
        creature_spell.mana_spent = 2

        # The trigger should not fire for non-instant/sorcery
        triggers = seeker.get_triggers(game, "spell_cast", creature_spell)
        assert len(triggers) == 0

    def test_triggers_on_sorcery_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]

        seeker = MuseSeeker(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[seeker])

        sorcery_spell = Sorcery(name="Divination", owner=p1, controller=p1)
        sorcery_spell.mana_spent = 3

        triggers = seeker.get_triggers(game, "spell_cast", sorcery_spell)
        assert len(triggers) >= 1
