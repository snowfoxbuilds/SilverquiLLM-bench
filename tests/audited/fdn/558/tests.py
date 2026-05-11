"""Audited tests for Tajuru Pathwarden (FDN collector number 558) — vigilance + trample."""

from __future__ import annotations

import pytest

from card_impl import TajuruPathwarden

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestTajuruPathwardenProperties:
    def test_is_creature(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        assert card.power == 5

    def test_toughness(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        assert card.toughness == 4

    def test_has_elf_subtype(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        assert "Elf" in card.subtypes

    def test_has_warrior_subtype(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        assert "Warrior" in card.subtypes


@pytest.mark.ability
class TestTajuruPathwardenKeywords:
    def test_has_vigilance(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_has_trample(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_exact_keywords(self) -> None:
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=None)
        expected = Keyword.VIGILANCE | Keyword.TRAMPLE
        assert card.keywords == expected


@pytest.mark.behavior
class TestTajuruPathwardenBehavior:
    """Vigilance + trample behavior tests."""

    def test_vigilance_does_not_tap_on_attack(self) -> None:
        """A creature with vigilance does not tap when declared as an attacker."""
        from tests.test_utils import create_game, set_board_state, declare_attackers

        game = create_game()
        card = TajuruPathwarden(name="Tajuru Pathwarden", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Tajuru Pathwarden"])
        assert not card.is_tapped

    def test_trample_excess_damage_goes_to_defending_player(self) -> None:
        """Tajuru Pathwarden (5/4, trample) blocked by a 2/2 deals 3 excess damage to defending player."""
        from tests.test_utils import create_game, set_board_state, declare_attackers, declare_blockers
        from engine.combat import combat_damage_step

        game = create_game()
        attacker = TajuruPathwarden(name="Tajuru Pathwarden", owner=game.players[0])
        attacker.summoning_sick = False
        set_board_state(game, 0, battlefield=[attacker])

        blocker = Creature(name="Bear", owner=game.players[1], base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[blocker])

        game.active_player_index = 0
        declare_attackers(game, ["Tajuru Pathwarden"])
        declare_blockers(game, {"Tajuru Pathwarden": ["Bear"]})
        combat_damage_step(game)

        # 5 power - 2 toughness lethal = 3 trample damage to defending player
        assert game.players[1].life == 20 - 3
