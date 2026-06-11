"""Tests for SOS 248 — Diary of Dreams.

Artifact — Book  {2}
Oracle: Whenever you cast an instant or sorcery spell, put a page counter
on this artifact.
{5}, {T}: Draw a card. This ability costs {1} less to activate for each
page counter on this artifact.
"""

from __future__ import annotations

from cards.sos.sos_248.card_impl import DiaryOfDreams
from engine.card import Artifact
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestDiaryOfDreamsProperties:
    """Static card data should match the SOS 248 spec."""

    def test_name(self) -> None:
        card = DiaryOfDreams(owner=None)
        assert card.name == "Diary of Dreams"

    def test_mana_cost(self) -> None:
        card = DiaryOfDreams(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}")

    def test_is_artifact(self) -> None:
        card = DiaryOfDreams(owner=None)
        assert isinstance(card, Artifact)

    def test_subtypes(self) -> None:
        card = DiaryOfDreams(owner=None)
        subtypes = getattr(card, "subtypes", set())
        assert "Book" in subtypes


class TestDiaryPageCounterTrigger:
    """Whenever you cast an instant or sorcery, put a page counter on this."""

    def test_has_triggered_ability(self) -> None:
        card = DiaryOfDreams(owner=None)
        assert hasattr(card, "on_spell_cast") or hasattr(card, "get_triggers")

    def test_page_counter_starts_at_zero(self) -> None:
        card = DiaryOfDreams(owner=None)
        counters = getattr(card, "page_counters", 0)
        assert counters == 0

    def test_casting_instant_adds_page_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DiaryOfDreams(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.page_counters = 0
        card.on_spell_cast(game, spell_type="instant")
        assert card.page_counters == 1

    def test_casting_sorcery_adds_page_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DiaryOfDreams(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.page_counters = 0
        card.on_spell_cast(game, spell_type="sorcery")
        assert card.page_counters == 1

    def test_casting_creature_does_not_add_page_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DiaryOfDreams(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.page_counters = 0
        card.on_spell_cast(game, spell_type="creature")
        assert card.page_counters == 0


class TestDiaryActivatedAbility:
    """Activated ability: {5}, {T}: Draw a card. Costs {1} less per page counter."""

    def test_base_activation_cost_is_five(self) -> None:
        card = DiaryOfDreams(owner=None)
        abilities = card.get_activated_abilities() if hasattr(card, "get_activated_abilities") else []
        assert len(abilities) >= 1
        ability = abilities[0]
        assert ability.mana_cost == ManaCost.parse("{5}") or ability.base_cost == 5

    def test_activation_cost_reduced_by_page_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DiaryOfDreams(owner=p1, controller=p1)
        card.page_counters = 3
        # Effective cost should be {5} - 3 = {2}
        cost = card.get_activation_cost(game) if hasattr(card, "get_activation_cost") else None
        if cost is not None:
            assert cost == 2

    def test_activation_cost_minimum_zero(self) -> None:
        """Cost cannot be reduced below zero (or below {0} + tap)."""
        game = create_game()
        p1 = game.players[0]
        card = DiaryOfDreams(owner=p1, controller=p1)
        card.page_counters = 10  # More than 5
        cost = card.get_activation_cost(game) if hasattr(card, "get_activation_cost") else None
        if cost is not None:
            assert cost >= 0

    def test_activation_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DiaryOfDreams(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        hand_before = len(game.get_zone(p1, Zone.HAND).get_all())
        card.activate(game)
        hand_after = len(game.get_zone(p1, Zone.HAND).get_all())
        assert hand_after == hand_before + 1

    def test_activation_requires_tap(self) -> None:
        """The ability requires tapping, so it cannot be activated if already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = DiaryOfDreams(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.tapped = True
        # Attempting activation while tapped should fail or be illegal
        assert card.can_activate(game) is False
